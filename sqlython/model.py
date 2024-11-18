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
    _query = {}

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

    def _process(self, reset=True):
        """
        Process the query
        """
        if not self.table:
            raise Exception('Table name is not defined')
        _q = copy.copy(self._query)
        if reset:
            self._query = {}
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
                ids = [row[main_field] for row in data]
                ids = [id for id in ids if id is not None]
                if not ids:
                    continue

                model = relation['model']
                model._query = {}
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
        If select is empty, it will select all fields
        :param fields: single string (comma separated), tuple, or list of fields
        """
        self._query['select'] = self._query.get('select', [])
        len_fields = len(fields)
        if len_fields > 0:
            if len_fields == 1:
                if isinstance(fields[0], str):
                    fields = [field.strip() for field in fields[0].split(',')]
                elif isinstance(fields[0], list):
                    fields = fields[0]
            self._query['select'] += fields
        return self

    def join(self, table, first, operator, second, join_type='INNER'):
        """
        JOIN table ON first operator second
        :param table: table name
        :param first: first field
        :param operator: operator
        :param second: second field
        :param join_type: join type (INNER, LEFT, RIGHT, FULL)
        """
        self._query['joins'] = self._query.get('joins', [])
        self._query['joins'].append(
            {'table': table, 'first': first, 'operator': operator, 'second': second, 'type': join_type})
        return self

    def left_join(self, table, first, operator, second):
        """
        LEFT JOIN table ON first operator second
        :param table: table name
        :param first: first field
        :param operator: operator
        :param second: second field
        """
        return self.join(table, first, operator, second, 'LEFT')

    def where(self, field, operator=None, value=None):
        """
        Add WHERE clause to query.
        If field is a dict, then treat it as equal operator with field as key and value as value.
        If field is a string, then treat it as equal operator with field as key and operator as value.
        If all arguments are present, then treat as it is.
        :param field: field name or dict
        :param operator: operator or value
        :param value: field value (if field and operator are present)
        """
        self._query['where'] = self._query.get('where', [])
        if isinstance(field, dict):
            for key, val in field.items():
                self._query['where'].append({'field': key, 'operator': '=', 'value': val, 'chain': 'AND'})
        elif isinstance(field, str):
            if not value:
                if not operator:
                    raise Exception('Second argument must be operator or value')
                value = operator
                operator = '='
            self._query['where'].append({'field': field, 'operator': operator, 'value': value, 'chain': 'AND'})
        return self

    def or_where(self, field, operator=None, value=None):
        """
        Add OR WHERE clause to query.
        If field is a dict, then treat it as equal operator with field as key and value as value.
        If field is a string, then treat it as equal operator with field as key and operator as value.
        If all arguments are present, then treat as it is.
        :param field: field name or dict
        :param operator: operator or value
        :param value: field value (if field and operator are present)
        """
        self._query['where'] = self._query.get('where', [])
        if isinstance(field, dict):
            for key, val in field.items():
                self._query['where'].append({
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
            self._query['where'].append({'field': field, 'operator': operator, 'value': value, 'chain': 'OR'})
        return self

    def where_raw(self, raw):
        """
        Add raw WHERE clause to query.
        :param raw: raw query string
        """
        self._query['where'] = self._query.get('where', [])
        self._query['where'].append({'raw': raw, 'chain': 'AND'})
        return self

    def or_where_raw(self, raw):
        """
        Add raw OR WHERE clause to query.
        :param raw: raw query string
        """
        self._query['where'] = self._query.get('where', [])
        self._query['where'].append({'raw': raw, 'chain': 'OR'})
        return self

    def where_in(self, field, values):
        """
        WHERE field IN (values)
        :param field: field name
        :param values: list of values
        """
        self._query['where'] = self._query.get('where', [])
        self._query['where'].append({'field': field, 'operator': 'IN', 'value': values, 'chain': 'AND'})
        return self

    def where_not_in(self, field, values):
        """
        WHERE field NOT IN (values)
        :param field: field name
        :param values: list of values
        """
        self._query['where'] = self._query.get('where', [])
        self._query['where'].append({'field': field, 'operator': 'NOT IN', 'value': values, 'chain': 'AND'})
        return self

    def where_null(self, field):
        """
        Add WHERE field IS NULL clause to query.
        :param field: field name
        """
        self._query['where'] = self._query.get('where', [])
        self._query['where'].append({'field': field, 'operator': 'IS', 'value': 'NULL', 'chain': 'AND'})
        return self

    def where_not_null(self, field):
        """
        Add WHERE field IS NOT NULL clause to query.
        :param field: field name
        """
        self._query['where'] = self._query.get('where', [])
        self._query['where'].append({'field': field, 'operator': 'IS NOT', 'value': 'NULL', 'chain': 'AND'})
        return self

    def with_trashed(self):
        """
        Include soft deleted data
        """
        self._query['with_trashed'] = True
        return self

    def order_by(self, field, direction='ASC'):
        """
        ORDER BY field direction
        :param field: field name
        :param direction: direction (ASC or DESC)
        """
        self._query['order_by'] = {'field': field, 'direction': direction}
        return self

    def group_by(self, *fields):
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
        self._query['group_by'] = fields
        return self

    def limit(self, limit, offset=0):
        """
        LIMIT limit OFFSET offset
        :param limit: number of data
        :param offset: offset
        """
        self._query['limit'] = limit
        self._query['offset'] = offset
        return self

    def has_many(self, model, foreign_key, local_key, name='', callback=None):
        """
        Add has_many relationship to result. Get all record that holds the current model primary key.
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
        self._query['relations'] = self._query.get('relations', [])
        self._query['relations'].append({
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
        Add has_one relationship to result. Get first record that holds the current model primary key.
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
        self._query['relations'] = self._query.get('relations', [])
        self._query['relations'].append({
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
        Add belongs_to relationship to result. Get first record that holds the related model primary key.
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
        self._query['relations'] = self._query.get('relations', [])
        self._query['relations'].append({
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
        Add with clause to query. This will add relationship data to result.
        :param relations: single string, list or tuple of relations
        """
        self._query['with'] = self._query.get('with', [])
        if len(relations) == 1:
            if isinstance(relations[0], str):
                relations = [relation.strip() for relation in relations[0].split(',')]
            elif isinstance(relations[0], list):
                relations = relations[0]
        for relation in relations:
            if not hasattr(self, relation):
                raise Exception(f'Relation `{relation}` doesn\'t exist!')
            getattr(self, relation)()
            # self._query['with'].append(relation)
        return self

    def raw_query(self, query):
        """
        Execute raw query
        :param query: query string
        """
        self._query['action'] = 'raw'
        return self._execute('raw', query)

    def get(self):
        """
        Get all data from the table
        """
        if self.soft_delete and not self._query.get('with_trashed'):
            self.where_null('deleted_at')
        self._query['action'] = 'select'
        return self._process()

    def first(self):
        """
        Get first data from the table
        """
        self._query['limit'] = 1
        result = self.get()
        return result[0] if result else None

    def find(self, primary_key):
        """
        Find data by primary key
        :param primary_key: primary key value
        """
        self._query['where'] = []
        return self.where(self.primary_key, primary_key).first()

    def count(self):
        """
        Get total data
        """
        self._query['select'] = ['COUNT(*) AS total']
        result = self.get()
        return result[0]['total'] if result else 0

    def insert(self, data):
        """
        Insert data
        :param data: data to be inserted
        """
        self._query['data'] = columns(data, self.fillable, self.guarded)
        if not self._query['data']:
            return None

        # cast data type if exist
        self._query['data'] = casts(self._query['data'], self.casts, True)

        if self.timestamp:
            self._query['data']['created_at'] = datetime.datetime.now()

        self._query['action'] = 'insert'
        return self._process()

    def update(self, data):
        self._query['data'] = columns(data, self.fillable, self.guarded)
        if not self._query['data']:
            return None

        # cast data type if exist
        self._query['data'] = casts(self._query['data'], self.casts, True)

        # for safety, update query must have where clause
        if self._query.get('where') is None:
            raise Exception('Update query must have where clause!')

        # check if soft delete is enabled
        if self.soft_delete and not self._query.get('with_trashed'):
            self.where_null('deleted_at')

        if self.timestamp:
            self._query['data']['updated_at'] = datetime.datetime.now()

        self._query['action'] = 'update'
        return self._process()

    @classmethod
    def delete(self):
        """
        Delete data. If soft delete is enabled, it will set `deleted_at` column to current datetime.
        """
        if self.soft_delete:
            self.where_null('deleted_at')
            self._query['data'] = {'deleted_at': datetime.datetime.now()}
            self._query['action'] = 'update'
        else:
            self._query['action'] = 'delete'
        return self._process()

    def restore(self):
        """
        Restore soft deleted data
        """
        if self.soft_delete:
            self._query['data'] = {'deleted_at': None}
            self._query['action'] = 'update'
            return self._process()
        return None

    def force_delete(self):
        """
        Force delete data. Delete data permanently even if soft delete is enabled.
        """
        self._query['action'] = 'delete'
        return self._process()

    def paginate(self, page=0, per_page=0):
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
            page = int((self._query.get('offset', 0) / self._query.get('limit', self.per_page)) + 1)
        if per_page < 1:
            per_page = self._query.get('limit', self.per_page)
        self._query['limit'] = per_page
        self._query['offset'] = (page - 1) * per_page

        if self.soft_delete and not self._query.get('with_trashed'):
            self.where_null('deleted_at')

        self._query['action'] = 'select'
        data = self._process(reset=False)

        if self.soft_delete and not self._query.get('with_trashed'):
            self._query['where'].pop()

        self._query['limit'] = None
        self._query['offset'] = None
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
