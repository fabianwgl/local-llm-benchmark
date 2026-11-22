"""PostgreSQL backend (psycopg2, threaded connection pool)."""
import contextlib

from tessera.storage.sql import SqlStore, _job


class PostgresStore(SqlStore):
    placeholder = "%s"

    def __init__(self, url, pool_size=5, statement_timeout=10.0):
        super().__init__()
        from psycopg2.pool import ThreadedConnectionPool

        options = "-c statement_timeout=%d" % int(statement_timeout * 1000)
        self._pool = ThreadedConnectionPool(1, pool_size, dsn=url, options=options)

    @contextlib.contextmanager
    def _connection(self):
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def record_attempt(self, job_id, decision):
        # Requeuing a dead-lettered job restarts its attempt numbers at 1, so the
        # history can already hold a row for this attempt.
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO job_attempts (job_id, attempt, error, delay_s, next_run_at, recorded_at) "
                "VALUES (%s, %s, %s, %s, %s, now()) "
                "ON CONFLICT (job_id, attempt) DO UPDATE SET error = EXCLUDED.error, delay_s = EXCLUDED.delay_s, "
                "next_run_at = EXCLUDED.next_run_at, recorded_at = now()",
                (job_id, decision.attempt, decision.error, decision.delay, decision.run_at),
            )

    def runnable_jobs(self, queues, limit):
        # SKIP LOCKED keeps busy workers from all reading the same head of the queue.
        with self._tx() as cur:
            cur.execute(
                "SELECT id, job_type, queue, state, priority, run_at, attempts, payload_size, payload, payload_ref, "
                "created_at, updated_at FROM jobs WHERE state = %s AND queue = ANY(%s) "
                "ORDER BY priority DESC, run_at, id LIMIT %s FOR UPDATE SKIP LOCKED",
                ("queued", list(queues), limit),
            )
            rows = cur.fetchall()
        return [_job(row) for row in rows]

    def close(self):
        self._pool.closeall()
