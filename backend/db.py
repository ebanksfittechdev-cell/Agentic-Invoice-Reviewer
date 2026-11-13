import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

_pool: pool.SimpleConnectionPool | None = None


def get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=os.environ["DATABASE_URL"],
        )
    return _pool


def get_db() -> psycopg2.extensions.connection:
    """Return a connection from the pool. Caller must call put_db() when done."""
    return get_pool().getconn()


def put_db(conn: psycopg2.extensions.connection) -> None:
    """Return a connection to the pool."""
    get_pool().putconn(conn)
