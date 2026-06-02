import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


class DatabaseConnection:
    DEFAULT_CONNECTION_NAME = "default"
    _connection_pools = {}

    @classmethod
    def initialize(
            cls,
            host=None,
            port=None,
            user=None,
            password=None,
            database=None,
            pool_name="sqlython_pool",
            pool_size=5,
            name=None,
            force=False,
    ):
        connection_name = name or cls.DEFAULT_CONNECTION_NAME
        if connection_name in cls._connection_pools and not force:
            return

        try:
            pool_identifier = pool_name if connection_name == cls.DEFAULT_CONNECTION_NAME else f"{pool_name}_{connection_name}"
            cls._connection_pools[connection_name] = mysql.connector.pooling.MySQLConnectionPool(
                pool_name=pool_identifier,
                pool_size=pool_size,
                pool_reset_session=True,
                host=host or os.getenv("DB_HOST", "localhost"),
                port=port or os.getenv("DB_PORT", 3306),
                user=user or os.getenv("DB_USER", "root"),
                password=password or os.getenv("DB_PASSWORD", ""),
                database=database or os.getenv("DB_NAME", "sqlython_db"),
            )
        except Exception as e:
            raise Exception("Failed to initialize connection:\n%s" % str(e))

    @classmethod
    def get_connection(cls, name=None):
        connection_name = name or cls.DEFAULT_CONNECTION_NAME
        if connection_name not in cls._connection_pools:
            cls.initialize(name=connection_name)  # Initialize automatically if not already done
        return cls._connection_pools[connection_name].get_connection()

    @classmethod
    def reset(cls, name=None):
        if name is None:
            cls._connection_pools = {}
            return
        cls._connection_pools.pop(name, None)
