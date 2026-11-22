"""Attempt-history helpers used by the 0.9 import tool.

These take a DB-API connection with qmark parameters rather than a Store.
"""
from tessera.util.timeutil import utcnow


def record_attempt(conn, job_id, attempt, error, next_run_at=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO job_attempts (job_id, attempt, error, delay_s, next_run_at, recorded_at) "
        "VALUES (?, ?, ?, NULL, ?, ?)",
        (job_id, attempt, error, next_run_at, utcnow()),
    )
    conn.commit()
    return cur.lastrowid


def attempts_for(conn, job_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT attempt, error, delay_s, next_run_at, recorded_at FROM job_attempts "
        "WHERE job_id = ? ORDER BY attempt",
        (job_id,),
    )
    return cur.fetchall()
