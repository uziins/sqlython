# Changelog

All notable changes to this project will be documented in this file.

## [1.4.0] - 2026-06-02

### Added

- **Multiple Connection Support**: Initialize and use multiple named database connections within a single Python process
  - New `DatabaseConnection.initialize(name='...', ...)` with named connection pools
  - New `Model.on(connection_name)` method for explicit connection selection
  - New `connection` class attribute for models to set a default named connection
  - New `DatabaseConnection.reset(name=None)` for connection pool cleanup
  - Automatic connection cascade for relationships (`has_many`, `has_one`, `belongs_to`)

### Changed

- `DatabaseConnection._execute()` is now an instance method (was static) to support per-model connection selection
- Backward compatible: existing code using default connection continues to work without changes

### Documentation

- Added "Multiple Connections (One Process)" section to README with two recommended approaches
- Created `MULTI_CONNECTION_GUIDE.md` with comprehensive architecture, best practices, and examples
- Added `examples/multi_connection_example.py` for quick start

### Testing

- Added 6 new unit tests covering multi-connection scenarios:
  - Named pool isolation (`test_named_pools_are_isolated`)
  - Dynamic connection selection (`test_model_on_uses_selected_connection`)
  - Class-level connection defaults (`test_class_level_connection_attribute`)
  - `.on()` override behavior (`test_on_overrides_class_level_connection`)
  - Default behavior without `.on()` (`test_default_connection_without_on`)
  - Relationship connection inheritance (`test_relation_inherits_parent_connection`)

### Example Usage

```python
from sqlython.connection import DatabaseConnection
from sqlython.model import Model

# Initialize multiple connections
DatabaseConnection.initialize(name='apollo', database='db_apollo', ...)
DatabaseConnection.initialize(name='olympus', database='db_olympus', ...)

# Approach 1: Dynamic selection
users = User().on('apollo').get()

# Approach 2: Class-level binding
class ApolloUser(Model):
    table = 'users'
    connection = 'apollo'

apollo_users = ApolloUser().get()
```

---

## [1.3.1] - Previous Releases

See git history for older versions.

