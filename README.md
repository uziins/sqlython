# SQLython

SQLython is a Python library that allows you to write SQL queries in Python. It is designed to be a simple and
easy-to-use tool for working with SQL databases in Python. Inspired by Eloquent in Laravel.

## Installation

```bash
pip install sqlython
```

## Configuration

### Environment Variables

Create a .env file in the root of your project and add the following variables:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_DATABASE=database
```

It will automatically create a connection to the database using the environment variables.
Alternatively, you can manually create a connection using the `DatabaseConnection` class. 
Just call the `initialize()` in the main file of your project.

```python
from sqlython.connection import DatabaseConnection

DatabaseConnection.initialize(
    host='localhost',
    port=3306,
    user='root',
    password='',
    database='database'
)
```

## Usage

### Extending the Model

i.e. users.py

```python
from sqlython.model import Model

class User(Model):
    table = 'users'
    fillable = ['name', 'username', 'email', 'password']
    hidden = ['password']
    timestamps = True
    soft_delete = True
    casts = {
            'is_active': 'boolean'
        }
```

### Usage

```python
from users import User
user = User.find(1)
```

### Retrieving Records

```python
users = User.where('is_active', True).get()
print(users)
```

## Model

### Class Attributes

#### table (str|required)

The name of the table in the database.

#### fillable (list)

The columns that are allowed to be assigned.

#### guarded (list)

The columns that are not allowed to be assigned.

#### hidden (list)

The columns that are hidden from the output.

#### timestamp (bool|default=True)

Automatically set the created_at and updated_at columns.

#### soft_delete (bool|default=False)

When set to True, the deleted_at column will be set to the current timestamp when a record is deleted.

#### per_page (int|default=10)

The default number of records to return per page when using the `paginate()` method.

#### casts (dict)

The columns that should be cast to a specific data type. Available data types are: `string`, `number`, `float`,
`boolean`, `date`, `json`.

## Methods

### get()

Retrieve all records from the database.

```python
users = User.get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 0 }
#     ...
# ]
```

### first()

Retrieve the first record from the database.

```python
user = User.first()

# { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 }
```

### find(id)

#### Parameters

- id (int|required) - The ID of the record to retrieve. Use self.primary_key to override the default primary key.

Get a record by its ID.

```python
user = User.find(1)

# { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 }
```

### count()

Get the number of records.

```python
count = User.count()

# 2
```

### paginate(page, per_page)

#### Parameters

- page (int|default=1) - The page number to retrieve.
- per_page (int|default=self.per_page) - The number of records to return per page.

Retrieve records paginated. Returns a dictionary with the following properties:

- data (list): The records for the current page.
- total (int): The total number of records.
- pages (int): The total number of pages.
- page (int): The current page number.
- per_page (int): The number of records per page.
- next_page (int|None): The next page number.
- prev_page (int|None): The previous page number.

```python
users = User.paginate(page=1, per_page=10)

# {
#     data: [
#         { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#         { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 0 }
#         ...
#     ],
#     total: 100,
#     pages: 10,
#     page: 1,
#     perPage: 10,
#     nextPage: 2,
#     prevPage: null
# }
```

### insert(data)

#### Parameters

- data (dict|required) - A dictionary of key-value pairs to insert into the database.

Insert a new record into the database.

```python
user = User.insert({
    'name': 'John Doe',
    'username': 'john_doe',
    'email': 'john@doe.com',
    'password': 'password'
})

# { insert_id: 1 }
```

### update(data)

#### Parameters

- data (dict|required) - A dictionary of key-value pairs to update in the database.

Update records in the database. Must be called after a `where()` method.

```python
User.where('id', 1).update({
    'name': 'Jane Doe',
    'username': 'jane_doe'
})

# { affected_rows: 1 }
```

### delete()

Delete records from the database. Must be called after a `where()` method.
If `soft_delete` is set to True, the record will be "soft deleted" by setting the `deleted_at` column to the current
timestamp.

```python
User.where('id', 1).delete()

# { affected_rows: 1 }
```

### restore()

Restore a "soft deleted" record by setting the `deleted_at` column to NULL. Must be called after a `where()` method.

```python
User.where('id', 1).restore()

# { affected_rows: 1 }
```

### force_delete()

Permanently delete records from the database whether `soft_delete` is set to True or False. Must be called after a
`where()` method.

```python
User.where('id', 1).force_delete()

# { affected_rows: 1 }
```

### select(columns)

#### Parameters

- columns (list|string|tuple) - The columns to select.

Select specific columns from the database.

```python
users = User.select('id', 'name').get()
# or
users = User.select(['id', 'name']).get()
# or
users = User.select('id, name').get()
# or
users = User.select('id').select('name').get()

# [
#     { id: 1, name: 'John Doe' },
#     { id: 2, name: 'Jane Doe' }
#     ...
# ]
```

### where(column, operator, value)

#### Parameters

- column (dict|string|required) - If a string, the column to filter by. If a dictionary, the key-value pairs to filter
  by.
- operator (string) - The operator to use for the comparison.
- value (string) - The value to compare against.

Filter records by a column value.
If column is a dictionary, the key-value pairs will be used to filter the records.
If column is a string and only has two arguments, the operator will default to `=` and the value will be the second
argument.
If all three arguments are provided, then treat it as it.

```python
users = User.where('is_active', 1).get()
# or
users = User.where({'is_active': 1}).get()
# or
users = User.where('is_actiove', '=', 1).get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 }
#     ...
# ]
```

### or_where(column, operator, value)

#### Parameters

- column (dict|string|required) - If a string, the column to filter by. If a dictionary, the key-value pairs to filter
  by.
- operator (string) - The operator to use for the comparison.
- value (string) - The value to compare against.

Same as [where()](#wherecolumn-operator-value) method. Adds an OR condition to the query.

```python
users = User.where('is_active', 1).or_where('username', 'john_doe').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 }
#     ...
# ]
```

### where_raw(query)

#### Parameters

- query (string|required) - The raw SQL query to filter records by.

Filter records by a raw SQL query.

```python
users = User.where_raw('is_active = 1').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 }
#     ...
# ]
```

### or_where_raw(query)

#### Parameters

- query (string|required) - The raw SQL query to filter records by.

Same as [where_raw()](#where_rawquery) method. Adds an OR condition to the query.

```python
users = User.where_raw('is_active = 1').or_where_raw('username = "john_doe"').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 }
#     ...
# ]
```

### where_in(column, values)

#### Parameters

- column (string|required) - The column to filter by.
- values (list|required) - The values to filter by.

Filter records by a column value that is in a list of values.

```python
users = User.where_in('id', [1, 2]).get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 }
#     ...
# ]
```

### where_not_in(column, values)

#### Parameters

- column (string|required) - The column to filter by.
- values (list|required) - The values to filter by.

Filter records by a column value that is not in a list of values.

```python
users = User.where_not_in('id', [1, 2]).get()

# [
#     { id: 3, name: 'John Smith', username: 'john_smith', is_active: 1 },
#     { id: 4, name: 'Jane Smith', username: 'jane_smith', is_active: 1 }
#     ...
# ]
```

### where_null(column)

#### Parameters

- column (string|required) - The column to filter by.

Filter records by a column value that is NULL.

```python
users = User.where_null('transferred_at').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1, transferred_at: None },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1, transferred_at: None }
#     ...
# ]
```

### where_not_null(column)

#### Parameters

- column (string|required) - The column to filter by.

Filter records by a column value that is not NULL.

```python
users = User.where_not_null('transferred_at').get()

# [
#     { id: 3, name: 'John Smith', username: 'john_smith', is_active: 1, transferred_at: '2024-01-01 00:00:00' },
#     { id: 4, name: 'Jane Smith', username: 'jane_smith', is_active: 1, transferred_at: '2024-03-05 00:00:00' }
#     ...
# ]
```

### with_trashed()

Include "soft deleted" records in the query.

```python
users = User.with_trashed().get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1, deleted_at: '2024-01-01 00:00:00' },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1, deleted_at: '2024-03-05 00:00:00' }
#     ...
# ]
```

### order_by(column, direction)

#### Parameters

- column (string|required) - The column to order by.
- direction (string|default='asc') - The direction to order by. Available options are: `asc`, `desc`.

Order records by a column.

```python
users = User.order_by('name', 'asc').get()

# [
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 },
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 }
#     ...
# ]
```

### group_by(column)

#### Parameters

- column (string|required) - The column to group by.

Group records by a column.

```python
users = User.select('count(id) as total', 'is_active').group_by('is_active').get()

# [
#     { total: 2, is_active: 1 },
#     { total: 2, is_active: 0 }
# ]
```

### limit(limit, offset)

#### Parameters

- limit (int|required) - The number of records to limit.
- offset (int|default=0) - The number of records to offset.

Limit the number of records returned.

```python
users = User.limit(2).get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 }
# ]
```

### join(table, first, operator, second, join_type)

#### Parameters

- table (string|required) - The table to join.
- first (string|required) - The first column to join on.
- operator (string|required) - The operator to use for the comparison.
- second (string|required) - The second column to join on.
- join_type (string|default='inner') - The type of join to perform. Available options are: `inner`, `left`, `right`,
  `full`.

Join another table to the query.

```python
users = User.join('profiles', 'users.id', '=', 'profiles.user_id').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1, user_id: 1, bio: 'Hello, World!' },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1, user_id: 2, bio: 'Goodbye, World!' }
#     ...
# ]
```

### left_join(table, first, operator, second)

#### Parameters

- table (string|required) - The table to join.
- first (string|required) - The first column to join on.
- operator (string|required) - The operator to use for the comparison.
- second (string|required) - The second column to join on.

Join another table to the query using a left join.

```python
users = User.left_join('profiles', 'users.id', '=', 'profiles.user_id').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1, user_id: 1, bio: 'Hello, World!' },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1, user_id: 2, bio: 'Goodbye, World!' }
#     ...
# ]
```

### has_one(table, foreign_key, local_key, name, callback)

#### Parameters

- table (string|required) - The table to join.
- foreign_key (string|required) - The foreign key column in the joined table.
- local_key (string|required) - The local key column in the current table.
- name (string) - The name of the relationship.
- callback (function) - The callback function to define the relationship.

Define a "has one" relationship between two tables.

```python
from profiles import Profile
from sqlython.model import Model


class User(Model):
    table = 'users'
    ...

    @classmethod
    def profile(cls):
        return cls.has_one(Profile, 'user_id', 'id', 'profile', lambda q: q.select('bio', 'user_id'))

```

### has_many(table, foreign_key, local_key, name, callback)

#### Parameters

- table (string|required) - The table to join.
- foreign_key (string|required) - The foreign key column in the joined table.
- local_key (string|required) - The local key column in the current table.
- name (string) - The name of the relationship.
- callback (function) - The callback function to define the relationship.

Define a "has many" relationship between two tables.

```python
from posts import Post
from sqlython.model import Model


class User(Model):
    table = 'users'
    ...

    @classmethod
    def posts(cls):
        return cls.has_many(Post, 'user_id', 'id', 'posts', lambda q: q.select('title', 'user_id'))

```

### belongs_to(table, foreign_key, local_key, name, callback)

#### Parameters

- table (string|required) - The table to join.
- foreign_key (string|required) - The foreign key column in the current table.
- local_key (string|required) - The local key column in the joined table.
- name (string) - The name of the relationship.
- callback (function) - The callback function to define the relationship.

Define a "belongs to" relationship between two tables.

```python
from users import User
from sqlython.model import Model


class Profile(Model):
    table = 'profiles'
    ...

    @classmethod
    def user(cls):
        return cls.belongs_to(User, 'user_id', 'id', 'user', lambda q: q.select('id', 'name', 'username'))

```

### with_relation(relation)

#### Parameters

- relation (string|list|tuple|required) - The name of the relationship to include.

Include a relationship in the query.

```python
users = User.with_relation('profile').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1, profile: { bio: 'Hello, World!' } },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1, profile: { bio: 'Goodbye, World!' } }
#     ...
# ]
```

### raw_query(query)

#### Parameters

- query (string|required) - The raw SQL query to execute.

Execute a raw SQL query.

```python
users = User.raw_query('SELECT * FROM users WHERE is_active = 1').get()

# [
#     { id: 1, name: 'John Doe', username: 'john_doe', is_active: 1 },
#     { id: 2, name: 'Jane Doe', username: 'jane_doe', is_active: 1 }
#     ...
# ]
```