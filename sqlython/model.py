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

    def __init__(self):
        self.__query = {}

    @staticmethod
    def _execute(action, query, bindings=None):
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

    def _process(self, reset=True):
        """
        Process the query.

        This method processes the query by executing it and handling the results. It supports casting data types,
        handling relationships, and hiding fields.

        Args:
            reset (bool, optional): Whether to reset the query after processing. Defaults to True.

        Returns:
            list or None: The processed query results, or None if an error occurs.
        """
        if not self.table:
            raise Exception('Table name is not defined')
        _q = copy.copy(self.__query)
        if reset:
            self.__query = {}
        query = query_builder(self.table, _q)
        try:
            data = self._execute(_q['action'], query['sql'], query['bindings'])
        except Exception as e:
            print(e)
            return None

        do_cast = _q['action'] == 'select' and len(self.casts) > 0
        do_relation = _q['action'] == 'select' and len(_q.get('relations', [])) > 0
        do_hide_field = _q['action'] == 'select' and len(self.hidden) > 0

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
                        raise Exception(f'Field `{main_field}` does not exist in model `{self.table}` result!')
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
                    row = casts(row, self.casts)
                if do_relation:
                    # iterate through relations and set data value
                    for identifier, relation in data_relation.items():
                        key = row[relation['key']]
                        if identifier in data_relation:
                            row[identifier] = relation['data'].get(key, relation['empty'])
                if do_hide_field:
                    for field in self.hidden:
                        row.pop(field, None)
                result_data.append(row)
        else:
            result_data = data

        return result_data

    def select(self, *fields):
        """
        Add SELECT clause to the query.

        This method adds the specified fields to the SELECT clause of the query. If no fields are provided,
        it will select all fields.

        Args:
            fields: A single string (comma separated), tuple, or list of fields to select.

        Returns:
            Model: The current model instance with the SELECT clause applied.
        """
        self.__query['select'] = self.__query.get('select', [])
        len_fields = len(fields)
        if len_fields > 0:
            if len_fields == 1:
                if isinstance(fields[0], str):
                    fields = [field.strip() for field in fields[0].split(',')]
                elif isinstance(fields[0], list):
                    fields = fields[0]
            self.__query['select'] += fields
        return self

    def join(self, table, first, operator, second, join_type='INNER'):
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
        self.__query['joins'] = self.__query.get('joins', [])
        self.__query['joins'].append(
            {'table': table, 'first': first, 'operator': operator, 'second': second, 'type': join_type})
        return self

    def left_join(self, table, first, operator, second):
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
        return self.join(table, first, operator, second, 'LEFT')

    def where(self, field, operator=None, value=None):
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
        self.__query['where'] = self.__query.get('where', [])
        if isinstance(field, dict):
            for key, val in field.items():
                self.__query['where'].append({'field': key, 'operator': '=', 'value': val, 'chain': 'AND'})
        elif isinstance(field, str):
            if not value:
                if not operator:
                    raise Exception('Second argument must be operator or value')
                value = operator
                operator = '='
            self.__query['where'].append({'field': field, 'operator': operator, 'value': value, 'chain': 'AND'})
        return self

    def or_where(self, field, operator=None, value=None):
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
        self.__query['where'] = self.__query.get('where', [])
        if isinstance(field, dict):
            for key, val in field.items():
                self.__query['where'].append({
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
            self.__query['where'].append({'field': field, 'operator': operator, 'value': value, 'chain': 'OR'})
        return self

    def where_raw(self, raw):
        """
        Add a raw WHERE clause to the query.

        This method adds a raw WHERE clause to the query, allowing for custom SQL conditions.

        Args:
            raw (str): The raw SQL condition to add to the WHERE clause.

        Returns:
            Model: The current model instance with the raw WHERE clause applied.
        """
        self.__query['where'] = self.__query.get('where', [])
        self.__query['where'].append({'raw': raw, 'chain': 'AND'})
        return self

    def or_where_raw(self, raw):
        """
        Add a raw OR WHERE clause to the query.

        This method adds a raw OR WHERE clause to the query, allowing for custom SQL conditions.

        Args:
            raw (str): The raw SQL condition to add to the OR WHERE clause.

        Returns:
            Model: The current model instance with the raw OR WHERE clause applied.
        """
        self.__query['where'] = self.__query.get('where', [])
        self.__query['where'].append({'raw': raw, 'chain': 'OR'})
        return self

    def where_in(self, field, values):
        """
        Add a WHERE IN clause to the query.

        This method adds a WHERE IN clause to the query, specifying the field and a list of values for the condition.

        Args:
            field (str): The field name to compare.
            values (list): A list of values to compare the field against.

        Returns:
            Model: The current model instance with the WHERE IN clause applied.
        """
        self.__query['where'] = self.__query.get('where', [])
        self.__query['where'].append({'field': field, 'operator': 'IN', 'value': values, 'chain': 'AND'})
        return self

    def where_not_in(self, field, values):
        """
        Add a WHERE NOT IN clause to the query.

        This method adds a WHERE NOT IN clause to the query, specifying the field and a list of values for the condition.

        Args:
            field (str): The field name to compare.
            values (list): A list of values to compare the field against.

        Returns:
            Model: The current model instance with the WHERE NOT IN clause applied.
        """
        self.__query['where'] = self.__query.get('where', [])
        self.__query['where'].append({'field': field, 'operator': 'NOT IN', 'value': values, 'chain': 'AND'})
        return self

    def where_null(self, field):
        """
        Add a WHERE IS NULL clause to the query.

        This method adds a WHERE IS NULL clause to the query, specifying the field to check for NULL values.

        Args:
            field (str): The field name to check for NULL values.

        Returns:
            Model: The current model instance with the WHERE IS NULL clause applied.
        """
        self.__query['where'] = self.__query.get('where', [])
        self.__query['where'].append({'field': field, 'operator': 'IS', 'value': 'NULL', 'chain': 'AND'})
        return self

    def where_not_null(self, field):
        """
        Add a WHERE IS NOT NULL clause to the query.

        This method adds a WHERE IS NOT NULL clause to the query, specifying the field to check for non-NULL values.

        Args:
            field (str): The field name to check for non-NULL values.

        Returns:
            Model: The current model instance with the WHERE IS NOT NULL clause applied.
        """
        self.__query['where'] = self.__query.get('where', [])
        self.__query['where'].append({'field': field, 'operator': 'IS NOT', 'value': 'NULL', 'chain': 'AND'})
        return self

    def with_trashed(self):
        """
        Include soft deleted data in the query results.

        This method modifies the query to include records that have been soft deleted.

        Returns:
            Model: The current model instance with the soft deleted data included.
        """
        self.__query['with_trashed'] = True
        return self

    def order_by(self, field, direction='ASC'):
        """
        Add an ORDER BY clause to the query.

        This method adds an ORDER BY clause to the query, specifying the field to order by and the direction of the order.

        Args:
            field (str): The field name to order by.
            direction (str, optional): The direction of the order (either 'ASC' for ascending or 'DESC' for descending). Defaults to 'ASC'.

        Returns:
            Model: The current model instance with the ORDER BY clause applied.
        """
        self.__query['order_by'] = {'field': field, 'direction': direction}
        return self

    def group_by(self, *fields):
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
        self.__query['group_by'] = fields
        return self

    def limit(self, limit, offset=0):
        """
        Set the LIMIT and OFFSET for the query.

        This method sets the limit and offset for the number of records to retrieve from the database.

        Args:
            limit (int): The number of records to retrieve.
            offset (int, optional): The number of records to skip before starting to retrieve records. Defaults to 0.

        Returns:
            Model: The current model instance with the limit and offset applied.
        """
        self.__query['limit'] = limit
        self.__query['offset'] = offset
        return self

    def has_many(self, model, foreign_key, local_key, name='', callback=None):
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
        self.__query['relations'] = self.__query.get('relations', [])
        self.__query['relations'].append({
            'model': model,
            'foreignKey': foreign_key,
            'localKey': local_key,
            'identifier': name,
            'type': 'hasMany',
            'callback': callback
        })
        return self

    def has_one(self, model, foreign_key, local_key, name='', callback=None):
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
        self.__query['relations'] = self.__query.get('relations', [])
        self.__query['relations'].append({
            'model': model,
            'foreignKey': foreign_key,
            'localKey': local_key,
            'identifier': name,
            'type': 'hasOne',
            'callback': callback
        })
        return self

    def belongs_to(self, model, foreign_key, local_key, name='', callback=None):
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
        self.__query['relations'] = self.__query.get('relations', [])
        self.__query['relations'].append({
            'model': model,
            'foreignKey': foreign_key,
            'localKey': local_key,
            'identifier': name,
            'type': 'belongsTo',
            'callback': callback
        })
        return self

    def with_relation(self, *relations):
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
            if not hasattr(self, relation):
                raise Exception(f'Relation `{relation}` doesn\'t exist!')
            getattr(self, relation)()
        return self

    def raw_query(self, query):
        """
        Execute a raw query.

        This method executes a raw SQL query.

        Args:
            query (str): The raw SQL query string to execute.

        Returns:
            Any: The result of the raw query execution.
        """
        self.__query['action'] = 'raw'
        return self._execute('raw', query)

    def get(self):
        """
        Retrieve all data from the table.

        This method retrieves all data from the table, applying any query conditions that have been set.

        Returns:
            list: A list of records from the table.
        """
        if self.soft_delete and not self.__query.get('with_trashed'):
            self.where_null('deleted_at')
        self.__query['action'] = 'select'
        return self._process()

    def first(self):
        """
        Retrieve the first record from the table.

        This method retrieves the first record from the table, applying any query conditions that have been set.

        Returns:
            dict: The first record from the table, or None if no record is found.
        """
        self.__query['limit'] = 1
        result = self.get()
        return result[0] if result else None

    def find(self, primary_key):
        """
        Find data by primary key.

        This method retrieves a single record from the database table based on the primary key value provided.

        Args:
            primary_key: The value of the primary key to search for.

        Returns:
            The first record that matches the primary key, or None if no record is found.
        """
        self.__query['where'] = []
        return self.where(self.primary_key, primary_key).first()

    def count(self):
        """
        Get the total number of records in the table.

        This method retrieves the total number of records in the table by executing a COUNT query.

        Returns:
            int: The total number of records in the table.
        """
        self.__query['select'] = ['COUNT(*) AS total']
        result = self.get()
        return result[0].get('total', 0) if result else 0

    def insert(self, *args, **kwargs):
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
        self.__query['data'] = columns(data, self.fillable, self.guarded)
        if not self.__query['data']:
            return None

        # cast data type if exist
        self.__query['data'] = casts(self.__query['data'], self.casts, True)

        if self.timestamp:
            self.__query['data']['created_at'] = datetime.datetime.now()

        self.__query['action'] = 'insert'
        return self._process()

    def update(self, *args, **kwargs):
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
        self.__query['data'] = columns(data, self.fillable, self.guarded)
        if not self.__query['data']:
            return None

        # cast data type if exist
        self.__query['data'] = casts(self.__query['data'], self.casts, True)

        # for safety, update query must have where clause
        if self.__query.get('where') is None:
            raise Exception('Update query must have where clause!')

        # check if soft delete is enabled
        if self.soft_delete and not self.__query.get('with_trashed'):
            self.where_null('deleted_at')

        if self.timestamp:
            self.__query['data']['updated_at'] = datetime.datetime.now()

        self.__query['action'] = 'update'
        return self._process()

    def delete(self):
        """
        Delete data. If soft delete is enabled, it will set `deleted_at` column to current datetime.

        This method deletes data from the database. If soft delete is enabled, it sets the `deleted_at` column
        to the current datetime instead of permanently deleting the record.

        Returns:
            Model: The current model instance with the delete operation applied.
        """
        if self.soft_delete:
            self.where_null('deleted_at')
            self.__query['data'] = {'deleted_at': datetime.datetime.now()}
            self.__query['action'] = 'update'
        else:
            self.__query['action'] = 'delete'
        return self._process()

    def restore(self):
        """
        Restore soft deleted data.

        This method restores data that has been soft deleted by setting the `deleted_at` column to None.

        Returns:
            The result of the update operation if soft delete is enabled, otherwise None.
        """
        if self.soft_delete:
            self.__query['data'] = {'deleted_at': None}
            self.__query['action'] = 'update'
            return self._process()
        return None

    def force_delete(self):
        """
        Force delete data.

        This method deletes data permanently from the database, even if soft delete is enabled.

        Returns:
            The result of the delete operation.
        """
        self.__query['action'] = 'delete'
        return self._process()

    def paginate(self, page=0, per_page=0):
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
            page = int((self.__query.get('offset', 0) / self.__query.get('limit', self.per_page)) + 1)
        if per_page < 1:
            per_page = self.__query.get('limit', self.per_page)
        self.__query['limit'] = per_page
        self.__query['offset'] = (page - 1) * per_page

        if self.soft_delete and not self.__query.get('with_trashed'):
            self.where_null('deleted_at')

        self.__query['action'] = 'select'
        data = self._process(reset=False)

        if self.soft_delete and not self.__query.get('with_trashed'):
            self.__query['where'].pop()

        self.__query['limit'] = None
        self.__query['offset'] = None
        total = self.count()
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
