import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

class DatabaseConnection:
    _connection_pool = None

    @classmethod
    def initialize(cls, host=None, port=None, user=None, password=None, database=None, pool_name="sqlython_pool", pool_size=5):
        if cls._connection_pool is None:
            try:
                cls._connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name=pool_name,
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
    def get_connection(cls):
        if cls._connection_pool is None:
            cls.initialize()  # Initialize automatically if not already done
        return cls._connection_pool.get_connection()
