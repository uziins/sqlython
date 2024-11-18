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
        Execute query
        :param query: query string
        :param bindings: query bindings
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
        Process the query
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
        If select is empty, it will select all fields
        :param fields: single string (comma separated), tuple, or list of fields
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
        JOIN table ON first operator second
        :param table: table name
        :param first: first field
        :param operator: operator
        :param second: second field
        :param join_type: join type (INNER, LEFT, RIGHT, FULL)
        """
        cls.__query['joins'] = cls.__query.get('joins', [])
        cls.__query['joins'].append(
            {'table': table, 'first': first, 'operator': operator, 'second': second, 'type': join_type})
        return cls

    @classmethod
    def left_join(cls, table, first, operator, second):
        """
        LEFT JOIN table ON first operator second
        :param table: table name
        :param first: first field
        :param operator: operator
        :param second: second field
        """
        return cls.join(table, first, operator, second, 'LEFT')

    @classmethod
    def where(cls, field, operator=None, value=None):
        """
        Add WHERE clause to query.
        If field is a dict, then treat it as equal operator with field as key and value as value.
        If field is a string, then treat it as equal operator with field as key and operator as value.
        If all arguments are present, then treat as it is.
        :param field: field name or dict
        :param operator: operator or value
        :param value: field value (if field and operator are present)
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
        Add OR WHERE clause to query.
        If field is a dict, then treat it as equal operator with field as key and value as value.
        If field is a string, then treat it as equal operator with field as key and operator as value.
        If all arguments are present, then treat as it is.
        :param field: field name or dict
        :param operator: operator or value
        :param value: field value (if field and operator are present)
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
        Add raw WHERE clause to query.
        :param raw: raw query string
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'raw': raw, 'chain': 'AND'})
        return cls

    @classmethod
    def or_where_raw(cls, raw):
        """
        Add raw OR WHERE clause to query.
        :param raw: raw query string
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'raw': raw, 'chain': 'OR'})
        return cls

    @classmethod
    def where_in(cls, field, values):
        """
        WHERE field IN (values)
        :param field: field name
        :param values: list of values
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'IN', 'value': values, 'chain': 'AND'})
        return cls

    @classmethod
    def where_not_in(cls, field, values):
        """
        WHERE field NOT IN (values)
        :param field: field name
        :param values: list of values
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'NOT IN', 'value': values, 'chain': 'AND'})
        return cls

    @classmethod
    def where_null(cls, field):
        """
        Add WHERE field IS NULL clause to query.
        :param field: field name
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'IS', 'value': 'NULL', 'chain': 'AND'})
        return cls

    @classmethod
    def where_not_null(cls, field):
        """
        Add WHERE field IS NOT NULL clause to query.
        :param field: field name
        """
        cls.__query['where'] = cls.__query.get('where', [])
        cls.__query['where'].append({'field': field, 'operator': 'IS NOT', 'value': 'NULL', 'chain': 'AND'})
        return cls

    @classmethod
    def with_trashed(cls):
        """
        Include soft deleted data
        """
        cls.__query['with_trashed'] = True
        return cls

    @classmethod
    def order_by(cls, field, direction='ASC'):
        """
        ORDER BY field direction
        :param field: field name
        :param direction: direction (ASC or DESC)
        """
        cls.__query['order_by'] = {'field': field, 'direction': direction}
        return cls

    @classmethod
    def group_by(cls, *fields):
        """
        GROUP BY fields
        :param fields: single string (with comma separated), tuple, or list of fields
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
        LIMIT limit OFFSET offset
        :param limit: number of data
        :param offset: offset
        """
        cls.__query['limit'] = limit
        cls.__query['offset'] = offset
        return cls

    @classmethod
    def has_many(cls, model, foreign_key, local_key, name='', callback=None):
        """
        Add hasMany relationship to result. Get all record that holds the current model primary key.
        :param model: model class
        :param foreign_key: foreign key. It's the related-model field that will be used to get the parent model
        :param local_key: local key. It's the field that the related-model will refer to
        :param name: identifier name. If not set, we use table name
        :param callback: callback function to modify query
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
        Add hasOne relationship to result. Get first record that holds the current model primary key.
        :param model: model class
        :param foreign_key: foreign key. It's the related-model field that will be used to get the parent model
        :param local_key: local key. It's the field that the related-model will refer to
        :param name: identifier name. If not set, we use table name
        :param callback: callback function to modify query
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
        Add belongsTo relationship to result. Get first record that holds the related model primary key.
        :param model: model class
        :param foreign_key: foreign key. It's the related-model field that will be used to get the parent model
        :param local_key: local key. It's the field that the related-model will refer to
        :param name: identifier name. If not set, we use table name
        :param callback: callback function to modify query
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
        Add with clause to query. This will add relationship data to result.
        :param relations: single string, list or tuple of relations
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
        Execute raw query
        :param query: query string
        """
        cls.__query['action'] = 'raw'
        return cls._execute('raw', query)

    @classmethod
    def get(cls):
        """
        Get all data from the table
        """
        if cls.soft_delete and not cls.__query.get('with_trashed'):
            cls.where_null('deleted_at')
        cls.__query['action'] = 'select'
        return cls._process()

    @classmethod
    def first(cls):
        """
        Get first data from the table
        """
        cls.__query['limit'] = 1
        result = cls.get()
        return result[0] if result else None

    @classmethod
    def find(cls, primary_key):
        """
        Find data by primary key
        :param primary_key: primary key value
        """
        cls.__query['where'] = []
        return cls.where(cls.primary_key, primary_key).first()

    @classmethod
    def count(cls):
        """
        Get total data
        """
        cls.__query['select'] = ['COUNT(*) AS total']
        result = cls.get()
        return result[0].get('total', 0) if result else 0

    @classmethod
    def insert(cls, data):
        """
        Insert data
        :param data: data to be inserted
        """
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
    def update(cls, data):
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
        Restore soft deleted data
        """
        if cls.soft_delete:
            cls.__query['data'] = {'deleted_at': None}
            cls.__query['action'] = 'update'
            return cls._process()
        return None

    @classmethod
    def force_delete(cls):
        """
        Force delete data. Delete data permanently even if soft delete is enabled.
        """
        cls.__query['action'] = 'delete'
        return cls._process()

    @classmethod
    def paginate(cls, page=0, per_page=0):
        """
        Get data with pagination
        :param page: page number
        :param per_page: number of rows per page
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
