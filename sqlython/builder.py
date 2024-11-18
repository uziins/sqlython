def query_builder(table, query):
    if query.get('raw_query'):
        return {'sql': query['raw_query'], 'bindings': []}
    action = query.get('action', 'select')

    bindings = []

    if action == 'select':
        sql_query = 'SELECT '
        if query.get('select'):
            sql_query += ', '.join(query.get('select'))
        else:
            sql_query += f'{table}.*'
            if query.get('joins'):
                for join in query.get('joins'):
                    sql_query += f', {join["table"]}.*'
        sql_query += f' FROM {table}'
    elif action == 'insert':
        if not query.get('data'):
            raise Exception('Insert query must have data!')
        sql_query = f'INSERT INTO {table}'
    elif action == 'update':
        if not query.get('data'):
            raise Exception('Update query must have data!')
        sql_query = f'UPDATE {table}'
    elif action == 'delete':
        if not query.get('where'):
            raise Exception('Delete query must have where clause!')
        sql_query = f'DELETE FROM {table}'
    else:
        raise Exception('Invalid __query.action')

    if action == 'update' or action == 'insert':
        sql_query += ' SET '
        for field, value in query.get('data').items():
            if value is None:
                sql_query += f'{field} = NULL, '
            elif isinstance(value, bool):
                sql_query += f'{field} = {1 if value else 0}, '
            else:
                sql_query += f'{field} = %s, '
                bindings.append(value)
        sql_query = sql_query[:-2]

    if query.get('joins'):
        for join in query.get('joins'):
            if '.' not in join['first']:
                join['first'] = f'{table}.{join["first"]}'
            if '.' not in join['second']:
                join['second'] = f'{join["table"]}.{join["second"]}'
            sql_query += f' {join["type"]} JOIN {join["table"]} ON {join["first"]} {join["operator"]} {join["second"]}'

    def write_where(where):
        sql = ''
        for i, clause in enumerate(where):
            if i > 0:
                sql += f' {clause["chain"]}'
            if clause.get('raw'):
                sql += f' {clause["raw"]}'
                continue
            new_field = clause['field']
            if '.' not in new_field:
                new_field = f'{table}.{clause["field"]}'
            if clause['operator'] in ['IN', 'NOT IN']:
                placeholders = ', '.join(['%s'] * len(clause['value']))
                sql += f' {new_field} {clause["operator"]} ({placeholders})'
                bindings.extend(clause['value'])
            elif clause['operator'] in ['IS', 'IS NOT']:
                sql += f' {new_field} {clause["operator"]} {clause["value"]}'
            else:
                sql += f' {new_field} {clause["operator"]} %s'
                bindings.append(clause['value'])
        return sql

    if query.get('where'):
        sql_query += ' WHERE'
        sql_query += write_where(query.get('where'))

    if query.get('order_by'):
        if query['order_by']['direction'] not in ['ASC', 'DESC']:
            query['order_by']['direction'] = 'ASC'
        if '.' not in query['order_by']['field']:
            query['order_by']['field'] = f'{table}.{query["order_by"]["field"]}'
        sql_query += f' ORDER BY {query["order_by"]["field"]} {query["order_by"]["direction"]}'

    if query.get('group_by'):
        sql_query += f' GROUP BY {", ".join(query["group_by"])}'

    if query.get('limit'):
        sql_query += ' LIMIT %s'
        bindings.append(int(query['limit']))
        if query.get('offset'):
            sql_query += ' OFFSET %s'
            bindings.append(int(query['offset']))

    return {'sql': sql_query, 'bindings': bindings}
