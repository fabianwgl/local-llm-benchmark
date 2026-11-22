"""Thin database helpers used across the app (PostgreSQL)."""
from contextlib import contextmanager

from app.pool import pool


def fetch_one(sql: str, params: tuple = ()):
    """Return the first row as a dict, or None. Values must be passed in `params`, never formatted
    into `sql`."""
    with pool.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """Run a statement and return the number of affected rows. Joins the current transaction if
    one is open; otherwise the statement is committed on its own."""
    with pool.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


@contextmanager
def transaction():
    """Run the enclosed statements atomically: commit on success, roll back on any exception."""
    with pool.transaction():
        yield
