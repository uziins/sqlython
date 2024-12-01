import copy
import datetime

from sqlython.builder import query_builder
from sqlython.connection import DatabaseConnection
from sqlython.filter import casts, columns

class Model:
    """
    This class is a base class for all models. It contains basic methods for CRUD operations.

    Attributes:
    - table: table name
    - primary_key: primary key field name
    - fillable: fillable fields
    - guarded: guarded fields
    - hidden: hidden fields
    - timestamp: whether to use timestamp
    - soft_delete: whether to use soft delete
    - per_page: number of data per page
    - casts: data type casting
    """

    table = ''
    primary_key = 'id'
    fillable = []
    guarded = []
    hidden = []
    timestamp = True
    soft_delete = False
    per_page = 10
    casts = {}
    __query = {}

    @classmethod
    def _execute(cls, action, query, bindings=None):
        """
        Execute a database query.

        This method executes a database query based on the specified action. It handles different types of queries
        such as insert, update, delete, and select. The method also manages the database connection and cursor.

        Args:
            action (str): The type of query to execute ('insert', 'update', 'delete', or other for select).
            query (str): The SQL query string to execute.
            bindings (list, optional): The query bindings to use. Defaults to None.

        Returns:
            dict or list: The result of the query execution. For 'insert', it returns a dictionary with the insert ID.
                          For 'update' and 'delete', it returns a dictionary with the number of affected rows.
                          For other actions, it returns a list of fetched records.
        """
        connection = DatabaseConnection.get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            if action == 'insert':
                cursor.execute(query, bindings)
                connection.commit()
                result = {'insert_id': cursor.lastrowid}
            elif action == 'update' or action == 'delete':
                cursor.execute(query, bindings)
                connection.commit()
                result = {'affected_rows': cursor.rowcount}
            else:
                cursor.execute(query, bindings)
                result = cursor.fetchall()
            return result
        finally:
            cursor.close()
            connection.close()

    @classmethod
    def _process(cls, reset=True):
        """
        Process the query.

        This method processes the query by executing it and handling the results. It supports casting data types,
        handling relationships, and hiding fields.

        Args:
            reset (bool, optional): Whether to reset the query after processing. Defaults to True.

        Returns:
            list or None: The processed query results, or None if an error occurs.
        """
        if not cls.table:
            raise Exception('Table name is not defined')
        _q = copy.copy(cls.__query)
        if reset:
            cls.__query = {}
        query = query_builder(cls.table, _q)
        try:
            data = cls._execute(_q['action'], query['sql'], query['bindings'])
        except Exception as e:
            print(e)
            return None

        do_cast = _q['action'] == 'select' and len(cls.casts) > 0
        do_relation = _q['action'] == 'select' and len(_q.get('relations', [])) > 0
        do_hide_field = _q['action'] == 'select' and len(cls.hidden) > 0

        # relation
        data_relation = {}
        if do_relation:
            # loop through each relation to get data
            for relation in _q.get('relations'):
                # get mainField, it's the field that will be used to get ids
                main_field = relation['foreignKey'] if relation['type'] == 'belongsTo' else relation['localKey']
                # get related ids, remove duplicate ids, and check if ids is not empty
                ids = []
                for row in data:
                    if main_field not in row:
                        raise Exception(f'Field `{main_field}` does not exist in model `{cls.table}` result!')
                    if row[main_field] is not None and row[main_field] not in ids:
                        ids.append(row[main_field])
                if not ids:
                    continue

                model = relation['model']
                model.__query['where'] = []
                model.__query['relations'] = []
                model.__query['select'] = []
                callback = relation['callback']
                if callback and callable(callback):
                    callback(model)
                # get relatedField, it's the field that will be used to get data using ids
                related_field = relation['localKey'] if relation['type'] == 'belongsTo' else relation['foreignKey']
                results = model.where_in(related_field, ids).get()
                data_relation[relation['identifier']] = {}
                if relation['type'] == 'belongsTo' or relation['type'] == 'hasOne':  # one to one
                    data_relation[relation['identifier']]['empty'] = None
                    data_relation[relation['identifier']]['key'] = main_field
                    data_relation[relation['identifier']]['data'] = {}
                    for row in results:
                        if not row.get(related_field):
                            raise Exception(f'Field `{related_field}` is not exist in relation result!')
                        data_relation[relation['identifier']]['data'][row[related_field]] = row
                else:  # has many
                    data_relation[relation['identifier']]['empty'] = []
                    data_relation[relation['identifier']]['key'] = main_field
                    data_relation[relation['identifier']]['data'] = {}
                    for row in results:
                        if not row.get(related_field):
                            raise Exception(f'Field `{related_field}` is not exist in relation result!')
                        if row[related_field] not in data_relation[relation['identifier']]['data']:
                            data_relation[relation['identifier']]['data'][row[related_field]] = []
                        data_relation[relation['identifier']]['data'][row[related_field]].append(row)

        # post process data
        if data and len(data) > 0 and (do_cast or do_relation or do_hide_field):
            result_data = []
            for row in data:
                if do_cast:
                    row = casts(row, cls.casts)
                if do_relation:
                    # iterate through relations and set data value
                    for identifier, relation in data_relation.items():
                        key = row[relation['key']]
                        if identifier in data_relation:
                            row[identifier] = relation['data'].get(key, relation['empty'])
                if do_hide_field:
                    for field in cls.hidden:
                        row.pop(field, None)
                result_data.append(row)
        else:
            result_data = data

        return result_data

    @classmethod
    def select(cls, *fields):
        """
        Add SELECT clause to the query.

        This method adds the specified fields to the SELECT clause of the query. If no fields are provided,
        it will select all fields.

        Args:
            fields: A single string (comma separated), tuple, or list of fields to select.

        Returns:
            Model: The current model instance with the SELECT clause applied.
        """
        cls.__query['select'] = cls.__query.get('select', [])
        len_fields = len(fields)
        if len_fields > 0:
            if len_fields == 1:
                if isinstance(fields[0], str):
                    fields = [field.strip() for field in fields[0].split(',')]
                elif isinstance(fields[0], list):
                    fields = fields[0]
            cls.__query['select'] += fields
        return cls

    @classmethod
    def join(cls, table, first, operator, second, join_type='INNER'):
        """
        Add a JOIN clause to the query.

        This method adds a JOIN clause to the query, specifying the table to join, the fields to join on,
        the operator to use, and the type of join.

        Args:
            table (str): The name of the table to join.
            first (str): The first field in the join condition.
            operator (str): The operator to use in the join condition (e.g., '=', '<>', etc.).
            second (str): The second field in the join condition.
            join_type (str, optional): The type of join to perform (e.g., 'INNER', 'LEFT', 'RIGHT', 'FULL'). Defaults to 'INNER'.

        Returns:
            Model: The current model instance with the JOIN clause applied.
        """
        cls.__query['joins'] = cls.__query.get('joins', [])
        cls.__query['joins'].append(
            {'table': table, 'first': first, 'operator': operator, 'second': second, 'type': join_type})
        return cls

    @classmethod
    def left_join(cls, table, first, operator, second):
        """
        Add a LEFT JOIN clause to the query.

        This method adds a LEFT JOIN clause to the query, specifying the table to join, the fields to join on,
        and the operator to use.

        Args:
            table (str): The name of the table to join.
            first (str): The first field in the join condition.
            operator (str): The operator to use in the join condition (e.g., '=', '<>', etc.).
            second (str): The second field in the join condition.

        Returns:
            Model: The current model instance with the LEFT JOIN clause applied.
        """
        return cls.join(table, first, operator, second, 'LEFT')

    @classmethod
    def where(cls, field, operator=None, value=None):
        """
        Add WHERE clause to query.
        If field is a dict, it will treat each key-value pair as a condition with the '=' operator.
        If field is a string, it will treat it as a condition with the specified operator and value.
        If only field and operator are provided, it will treat the operator as the value and use '=' as the operator.

        Args:
            field (str or dict): The field name or a dictionary of field-value pairs.
            operator (str, optional): The operator to use in the condition (e.g., '=', '<>', etc.). Defaults to None.
            value (any, optional): The value to compare the field against. Defaults to None.

        Returns:
            Model: The current model instance with the WHERE clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        if isinstance(field, dict):
            for key, val in field.items():
                cls.__query['where'].append({'field': key, 'operator': '=', 'value': val, 'chain': 'AND'})
        elif isinstance(field, str):
            if not value:
                if not operator:
                    raise Exception('Second argument must be operator or value')
                value = operator
                operator = '='
            cls.__query['where'].append({'field': field, 'operator': operator, 'value': value, 'chain': 'AND'})
        return cls

    @classmethod
    def or_where(cls, field, operator=None, value=None):
        """
        Add an OR WHERE clause to the query.

        This method adds an OR WHERE clause to the query, specifying the field, operator, and value for the condition.
        If the field is a dictionary, it treats each key-value pair as a condition with the '=' operator.
        If the field is a string, it treats it as a condition with the specified operator and value.
        If only the field and operator are provided, it treats the operator as the value and uses '=' as the operator.

        Args:
            field (str or dict): The field name or a dictionary of field-value pairs.
            operator (str, optional): The operator to use in the condition (e.g., '=', '<>', etc.). Defaults to None.
            value (any, optional): The value to compare the field against. Defaults to None.

        Returns:
            Model: The current model instance with the OR WHERE clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        if isinstance(field, dict):
            for key, val in field.items():
                cls.__query['where'].append({
                    'field': key,
                    'operator': '=',
                    'value': val,
                    'chain': 'OR'
                })
        elif isinstance(field, str):
            if not value:
                if not operator:
                    raise Exception('Second argument must be operator or value')
                value = operator
                operator = '='
            cls.__query['where'].append({'field': field, 'operator': operator, 'value': value, 'chain': 'OR'})
        return cls

    @classmethod
    def where_raw(cls, raw):
        """
        Add a raw WHERE clause to the query.

        This method adds a raw WHERE clause to the query, allowing for custom SQL conditions.

        Args:
            raw (str): The raw SQL condition to add to the WHERE clause.

        Returns:
            Model: The current model instance with the raw WHERE clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'raw': raw, 'chain': 'AND'})
        return cls

    @classmethod
    def or_where_raw(cls, raw):
        """
        Add a raw OR WHERE clause to the query.

        This method adds a raw OR WHERE clause to the query, allowing for custom SQL conditions.

        Args:
            raw (str): The raw SQL condition to add to the OR WHERE clause.

        Returns:
            Model: The current model instance with the raw OR WHERE clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'raw': raw, 'chain': 'OR'})
        return cls

    @classmethod
    def where_in(cls, field, values):
        """
        Add a WHERE IN clause to the query.

        This method adds a WHERE IN clause to the query, specifying the field and a list of values for the condition.

        Args:
            field (str): The field name to compare.
            values (list): A list of values to compare the field against.

        Returns:
            Model: The current model instance with the WHERE IN clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'IN', 'value': values, 'chain': 'AND'})
        return cls

    @classmethod
    def where_not_in(cls, field, values):
        """
        Add a WHERE NOT IN clause to the query.

        This method adds a WHERE NOT IN clause to the query, specifying the field and a list of values for the condition.

        Args:
            field (str): The field name to compare.
            values (list): A list of values to compare the field against.

        Returns:
            Model: The current model instance with the WHERE NOT IN clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'NOT IN', 'value': values, 'chain': 'AND'})
        return cls

    @classmethod
    def where_null(cls, field):
        """
        Add a WHERE IS NULL clause to the query.

        This method adds a WHERE IS NULL clause to the query, specifying the field to check for NULL values.

        Args:
            field (str): The field name to check for NULL values.

        Returns:
            Model: The current model instance with the WHERE IS NULL clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'IS', 'value': 'NULL', 'chain': 'AND'})
        return cls

    @classmethod
    def where_not_null(cls, field):
        """
        Add a WHERE IS NOT NULL clause to the query.

        This method adds a WHERE IS NOT NULL clause to the query, specifying the field to check for non-NULL values.

        Args:
            field (str): The field name to check for non-NULL values.

        Returns:
            Model: The current model instance with the WHERE IS NOT NULL clause applied.
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'IS NOT', 'value': 'NULL', 'chain': 'AND'})
        return cls

    @classmethod
    def with_trashed(cls):
        """
        Include soft deleted data in the query results.

        This method modifies the query to include records that have been soft deleted.

        Returns:
            Model: The current model instance with the soft deleted data included.
        """
        cls.__query['with_trashed'] = True
        return cls

    @classmethod
    def order_by(cls, field, direction='ASC'):
        """
        Add an ORDER BY clause to the query.

        This method adds an ORDER BY clause to the query, specifying the field to order by and the direction of the order.

        Args:
            field (str): The field name to order by.
            direction (str, optional): The direction of the order (either 'ASC' for ascending or 'DESC' for descending). Defaults to 'ASC'.

        Returns:
            Model: The current model instance with the ORDER BY clause applied.
        """
        cls.__query['order_by'] = {'field': field, 'direction': direction}
        return cls

    @classmethod
    def group_by(cls, *fields):
        """
        Add a GROUP BY clause to the query.

        This method adds a GROUP BY clause to the query, specifying the fields to group by.

        Args:
            fields: A single string (comma separated), tuple, or list of fields to group by.

        Returns:
            Model: The current model instance with the GROUP BY clause applied.
        """
        len_fields = len(fields)
        if len_fields == 1:
            if isinstance(fields[0], str):
                fields = [field.strip() for field in fields[0].split(',')]
            elif isinstance(fields[0], list):
                fields = fields[0]
        cls.__query['group_by'] = fields
        return cls

    @classmethod
    def limit(cls, limit, offset=0):
        """
        Set the LIMIT and OFFSET for the query.

        This method sets the limit and offset for the number of records to retrieve from the database.

        Args:
            limit (int): The number of records to retrieve.
            offset (int, optional): The number of records to skip before starting to retrieve records. Defaults to 0.

        Returns:
            Model: The current model instance with the limit and offset applied.
        """
        cls.__query['limit'] = limit
        cls.__query['offset'] = offset
        return cls

    @classmethod
    def has_many(cls, model, foreign_key, local_key, name='', callback=None):
        """
        Add a hasMany relationship to the result.

        This method adds a hasMany relationship to the result, retrieving all records that hold the current model's primary key.

        Args:
            model (Model): The related model class.
            foreign_key (str): The foreign key field in the related model.
            local_key (str): The local key field in the current model.
            name (str, optional): The identifier name for the relationship. Defaults to the table name of the related model.
            callback (function, optional): A callback function to modify the query.

        Returns:
            Model: The current model instance with the hasMany relationship applied.
        """
        if isinstance(model, type):
            model = model()
        if not name:
            name = model.table
        cls.__query['relations'] = cls.__query.get('relations', [])
        cls.__query['relations'].append({
            'model': model,
            'foreignKey': foreign_key,
            'localKey': local_key,
            'identifier': name,
            'type': 'hasMany',
            'callback': callback
        })
        return cls

    @classmethod
    def has_one(cls, model, foreign_key, local_key, name='', callback=None):
        """
        Add a hasOne relationship to the result.

        This method adds a hasOne relationship to the result, retrieving the first record that holds the current model's primary key.

        Args:
            model (Model): The related model class.
            foreign_key (str): The foreign key field in the related model.
            local_key (str): The local key field in the current model.
            name (str, optional): The identifier name for the relationship. Defaults to the table name of the related model.
            callback (function, optional): A callback function to modify the query.

        Returns:
            Model: The current model instance with the hasOne relationship applied.
        """
        if isinstance(model, type):
            model = model()
        if not name:
            name = model.table
        cls.__query['relations'] = cls.__query.get('relations', [])
        cls.__query['relations'].append({
            'model': model,
            'foreignKey': foreign_key,
            'localKey': local_key,
            'identifier': name,
            'type': 'hasOne',
            'callback': callback
        })
        return cls

    @classmethod
    def belongs_to(cls, model, foreign_key, local_key, name='', callback=None):
        """
        Add a belongsTo relationship to the result.

        This method adds a belongsTo relationship to the result, retrieving the first record that holds the related model's primary key.

        Args:
            model (Model): The related model class.
            foreign_key (str): The foreign key field in the related model.
            local_key (str): The local key field in the current model.
            name (str, optional): The identifier name for the relationship. Defaults to the table name of the related model.
            callback (function, optional): A callback function to modify the query.

        Returns:
            Model: The current model instance with the belongsTo relationship applied.
        """
        if isinstance(model, type):
            model = model()
        if not name:
            name = model.table
        cls.__query['relations'] = cls.__query.get('relations', [])
        cls.__query['relations'].append({
            'model': model,
            'foreignKey': foreign_key,
            'localKey': local_key,
            'identifier': name,
            'type': 'belongsTo',
            'callback': callback
        })
        return cls

    @classmethod
    def with_relation(cls, *relations):
        """
        Add a with clause to the query.

        This method adds relationship data to the result by including the specified relations.

        Args:
            relations: A single string, list, or tuple of relations to include.

        Returns:
            Model: The current model instance with the specified relations included.
        """
        if len(relations) == 1:
            if isinstance(relations[0], str):
                relations = [relation.strip() for relation in relations[0].split(',')]
            elif isinstance(relations[0], list):
                relations = relations[0]
        for relation in relations:
            if not hasattr(cls, relation):
                raise Exception(f'Relation `{relation}` doesn\'t exist!')
            getattr(cls, relation)()
        return cls

    @classmethod
    def raw_query(cls, query):
        """
        Execute a raw query.

        This method executes a raw SQL query.

        Args:
            query (str): The raw SQL query string to execute.

        Returns:
            Any: The result of the raw query execution.
        """
        cls.__query['action'] = 'raw'
        return cls._execute('raw', query)

    @classmethod
    def get(cls):
        """
        Retrieve all data from the table.

        This method retrieves all data from the table, applying any query conditions that have been set.

        Returns:
            list: A list of records from the table.
        """
        if cls.soft_delete and not cls.__query.get('with_trashed'):
            cls.where_null('deleted_at')
        cls.__query['action'] = 'select'
        return cls._process()

    @classmethod
    def first(cls):
        """
        Retrieve the first record from the table.

        This method retrieves the first record from the table, applying any query conditions that have been set.

        Returns:
            dict: The first record from the table, or None if no record is found.
        """
        cls.__query['limit'] = 1
        result = cls.get()
        return result[0] if result else None

    @classmethod
    def find(cls, primary_key):
        """
        Find data by primary key.

        This method retrieves a single record from the database table based on the primary key value provided.

        Args:
            primary_key: The value of the primary key to search for.

        Returns:
            The first record that matches the primary key, or None if no record is found.
        """
        cls.__query['where'] = []
        return cls.where(cls.primary_key, primary_key).first()

    @classmethod
    def count(cls):
        """
        Get the total number of records in the table.

        This method retrieves the total number of records in the table by executing a COUNT query.

        Returns:
            int: The total number of records in the table.
        """
        cls.__query['select'] = ['COUNT(*) AS total']
        result = cls.get()
        return result[0].get('total', 0) if result else 0

    @classmethod
    def insert(cls, *args, **kwargs):
        """
        Insert data into the database.

        This method inserts the data into the database for the model. It accepts data as either a dictionary
        or keyword arguments. The data is filtered based on the fillable and guarded fields, and the data types
        are cast if necessary. The method also handles timestamp fields if enabled.

        Args:
            *args: Variable length argument list. The first argument can be a dictionary containing the data to insert.
            **kwargs: Arbitrary keyword arguments containing the data to insert.

        Returns:
            The result of the insert operation, or None if no data is provided.
        """
        data = args[0] if args and isinstance(args[0], dict) else kwargs
        cls.__query['data'] = columns(data, cls.fillable, cls.guarded)
        if not cls.__query['data']:
            return None

        # cast data type if exist
        cls.__query['data'] = casts(cls.__query['data'], cls.casts, True)

        if cls.timestamp:
            cls.__query['data']['created_at'] = datetime.datetime.now()

        cls.__query['action'] = 'insert'
        return cls._process()

    @classmethod
    def update(cls, *args, **kwargs):
        """
        Update data in the database.

        This method updates the data in the database for the model. It accepts data as either a dictionary
        or keyword arguments. The data is filtered based on the fillable and guarded fields, and the data types
        are cast if necessary. The method ensures that an update query has a WHERE clause for safety and handles
        soft delete and timestamp fields if enabled.

        Args:
            *args: Variable length argument list. The first argument can be a dictionary containing the data to update.
            **kwargs: Arbitrary keyword arguments containing the data to update.

        Returns:
            The result of the update operation, or None if no data is provided.
        """
        data = args[0] if args and isinstance(args[0], dict) else kwargs
        cls.__query['data'] = columns(data, cls.fillable, cls.guarded)
        if not cls.__query['data']:
            return None

        # cast data type if exist
        cls.__query['data'] = casts(cls.__query['data'], cls.casts, True)

        # for safety, update query must have where clause
        if cls.__query.get('where') is None:
            raise Exception('Update query must have where clause!')

        # check if soft delete is enabled
        if cls.soft_delete and not cls.__query.get('with_trashed'):
            cls.where_null('deleted_at')

        if cls.timestamp:
            cls.__query['data']['updated_at'] = datetime.datetime.now()

        cls.__query['action'] = 'update'
        return cls._process()

    @classmethod
    def delete(cls):
        """
        Delete data. If soft delete is enabled, it will set `deleted_at` column to current datetime.

        This method deletes data from the database. If soft delete is enabled, it sets the `deleted_at` column
        to the current datetime instead of permanently deleting the record.

        Returns:
            Model: The current model instance with the delete operation applied.
        """
        if cls.soft_delete:
            cls.where_null('deleted_at')
            cls.__query['data'] = {'deleted_at': datetime.datetime.now()}
            cls.__query['action'] = 'update'
        else:
            cls.__query['action'] = 'delete'
        return cls._process()

    @classmethod
    def restore(cls):
        """
        Restore soft deleted data.

        This method restores data that has been soft deleted by setting the `deleted_at` column to None.

        Returns:
            The result of the update operation if soft delete is enabled, otherwise None.
        """
        if cls.soft_delete:
            cls.__query['data'] = {'deleted_at': None}
            cls.__query['action'] = 'update'
            return cls._process()
        return None

    @classmethod
    def force_delete(cls):
        """
        Force delete data.

        This method deletes data permanently from the database, even if soft delete is enabled.

        Returns:
            The result of the delete operation.
        """
        cls.__query['action'] = 'delete'
        return cls._process()

    @classmethod
    def paginate(cls, page=0, per_page=0):
        """
        Get data with pagination.

        This method retrieves data from the database table with pagination. It calculates the offset and limit
        based on the provided page number and number of rows per page. It also handles soft delete filtering
        if enabled.

        Args:
            page (int): Page number. Defaults to 0.
            per_page (int): Number of rows per page. Defaults to 0.

        Returns:
            dict: A dictionary containing the paginated data, total number of records, total pages, current page,
                  number of rows per page, next page number, and previous page number.
        """
        if not isinstance(page, int):
            page = int(page)
        if not isinstance(per_page, int):
            per_page = int(per_page)
        if page < 1:
            page = int((cls.__query.get('offset', 0) / cls.__query.get('limit', cls.per_page)) + 1)
        if per_page < 1:
            per_page = cls.__query.get('limit', cls.per_page)
        cls.__query['limit'] = per_page
        cls.__query['offset'] = (page - 1) * per_page

        if cls.soft_delete and not cls.__query.get('with_trashed'):
            cls.where_null('deleted_at')

        cls.__query['action'] = 'select'
        data = cls._process(reset=False)

        if cls.soft_delete and not cls.__query.get('with_trashed'):
            cls.__query['where'].pop()

        cls.__query['limit'] = None
        cls.__query['offset'] = None
        total = cls.count()
        pages = int(total / per_page)
        return {
            'data': data,
            'total': total,
            'pages': pages,
            'page': page,
            'per_page': per_page,
            'next_page': page + 1 if page < pages else None,
            'prev_page': page - 1 if 1 < page <= pages else None
        }
