import mysql.connector
from mysql.connector import pooling

# OPTIMIZATION: Connection pooling for performance
# Reuses connections instead of creating new ones for each query
_connection_pool = None

def _get_connection_pool(cfg):
    """Get or create the global connection pool"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pooling.MySQLConnectionPool(
            pool_name="portfolio_pool",
            pool_size=5,  # Max 5 concurrent connections
            pool_reset_session=True,
            **cfg
        )
        print("✓ MySQL connection pool created (size=5)")
    return _connection_pool

class MysqlDB:

    def __init__(self, cfg):
        # OPTIMIZATION: Get connection from pool instead of creating new one
        pool = _get_connection_pool(cfg)
        self._conn = pool.get_connection()
        self._cursor = self._conn.cursor()
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def connection(self):
        return self._conn

    @property
    def cursor(self):
        return self._cursor

    def commit(self):
        self.connection.commit()

    def close(self, commit=True):
        if commit:
            self.commit()
        self.connection.close()

    def execute(self, sql, params=None):
        self.cursor.execute(sql, params or ())

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()

    def query(self, sql, params=None):
        self.cursor.execute(sql, params or ())
        return self.fetchall()

    def create_index_safe(self, sql):
        """Execute a CREATE INDEX statement, ignoring if index already exists.

        MySQL error 1061 = Duplicate key name (index already exists).
        """
        try:
            self.cursor.execute(sql)
        except mysql.connector.errors.ProgrammingError as e:
            if e.errno == 1061:  # Duplicate key name
                pass
            else:
                raise