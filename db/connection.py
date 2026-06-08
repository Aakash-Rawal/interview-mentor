"""PostgreSQL connection pool, shared across all agents.

A single ThreadedConnectionPool is created lazily on first use so importing
this module never requires a live database (keeps tests/imports cheap).
"""
from contextlib import contextmanager

from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

import config

_pool: ThreadedConnectionPool | None = None


def get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            minconn=1, maxconn=10, dsn=config.DATABASE_URL
        )
    return _pool


@contextmanager
def get_cursor(commit: bool = False):
    """Borrow a connection from the pool and yield a dict cursor.

    Usage:
        with get_cursor(commit=True) as cur:
            cur.execute("INSERT ...")
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
