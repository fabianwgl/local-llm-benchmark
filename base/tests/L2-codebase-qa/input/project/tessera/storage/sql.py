"""SQL implementation shared by the SQLite and PostgreSQL backends.

Statements are written with qmark (?) parameters; _q() rewrites them for
drivers that use another style. Subclasses provide _connection().
"""
import contextlib
import json
import logging
from datetime import timedelta
from pathlib import Path

from tessera.config.env import DEBUG_SQL, flag
from tessera.errors import JobNotFound, RunNotFound
from tessera.models import Job, JobState, Run, RunState
from tessera.storage.base import Store
from tessera.util import new_id
from tessera.util.timeutil import ensure_utc, utcnow

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_JOB_COLUMNS = ("id, job_type, queue, state, priority, run_at, attempts, payload_size, payload, payload_ref, "
                "created_at, updated_at")
_RUN_COLUMNS = "id, job_id, attempt, owner, state, started_at, lease_until, finished_at, error, output"


class SqlStore(Store):
    placeholder = "?"

    def __init__(self):
        self._debug = flag(DEBUG_SQL)

    def _connection(self):
        raise NotImplementedError

    @contextlib.contextmanager
    def _tx(self):
        with self._connection() as conn:
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                cur.close()

    def _q(self, sql):
        if self._debug:
            log.debug("sql: %s", sql)
        return sql if self.placeholder == "?" else sql.replace("?", self.placeholder)

    # jobs ------------------------------------------------------------------
    def insert_job(self, spec, stored):
        now = utcnow()
        job_id = new_id("job")
        state = JobState.SCHEDULED if spec.run_at is not None and spec.run_at > now else JobState.QUEUED
        with self._tx() as cur:
            cur.execute(self._q("INSERT INTO jobs (" + _JOB_COLUMNS + ") VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)"),
                        (job_id, spec.job_type, spec.queue, state, spec.priority, spec.run_at or now,
                         stored.size, stored.inline, stored.ref, now, now))
        return self.get_job(job_id)

    def get_job(self, job_id):
        with self._tx() as cur:
            cur.execute(self._q("SELECT " + _JOB_COLUMNS + " FROM jobs WHERE id = ?"), (job_id,))
            row = cur.fetchone()
        if row is None:
            raise JobNotFound(job_id)
        return _job(row)

    def list_jobs(self, state=None, queue=None, limit=100, after=None):
        clauses, params = [], []
        for column, value in (("state", state), ("queue", queue)):
            if value is not None:
                clauses.append(column + " = ?")
                params.append(value)
        if after is not None:
            clauses.append("id > ?")
            params.append(after)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._tx() as cur:
            cur.execute(self._q("SELECT " + _JOB_COLUMNS + " FROM jobs" + where + " ORDER BY id LIMIT ?"),
                        params + [limit])
            return [_job(row) for row in cur.fetchall()]

    def set_state(self, job_id, state):
        with self._tx() as cur:
            cur.execute(self._q("UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?"), (state, utcnow(), job_id))

    def reschedule(self, job_id, run_at):
        with self._tx() as cur:
            cur.execute(self._q("UPDATE jobs SET state = ?, run_at = ?, updated_at = ? WHERE id = ?"),
                        (JobState.SCHEDULED, run_at, utcnow(), job_id))

    def runnable_jobs(self, queues, limit):
        marks = ", ".join("?" for _ in queues)
        with self._tx() as cur:
            cur.execute(self._q("SELECT " + _JOB_COLUMNS + " FROM jobs WHERE state = ? AND queue IN (" + marks + ") "
                                "ORDER BY priority DESC, run_at, id LIMIT ?"),
                        [JobState.QUEUED] + list(queues) + [limit])
            return [_job(row) for row in cur.fetchall()]

    def promote_due(self, now):
        with self._tx() as cur:
            cur.execute(self._q("UPDATE jobs SET state = ?, updated_at = ? WHERE state = ? AND run_at <= ?"),
                        (JobState.QUEUED, now, JobState.SCHEDULED, now))
            return cur.rowcount

    # runs and attempts -----------------------------------------------------
    def start_run(self, job_id, owner, lease_until):
        now = utcnow()
        run_id = new_id("run")
        with self._tx() as cur:
            cur.execute(self._q("UPDATE jobs SET state = ?, attempts = attempts + 1, updated_at = ? "
                                "WHERE id = ? AND state = ?"), (JobState.RUNNING, now, job_id, JobState.QUEUED))
            if cur.rowcount != 1:
                return None
            cur.execute(self._q("SELECT attempts FROM jobs WHERE id = ?"), (job_id,))
            attempt = cur.fetchone()[0]
            cur.execute(self._q("INSERT INTO runs (id, job_id, attempt, owner, state, started_at, lease_until) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)"),
                        (run_id, job_id, attempt, owner, RunState.RUNNING, now, lease_until))
        return Run(run_id, job_id, attempt, owner, RunState.RUNNING, now, lease_until)

    def finish_run(self, run_id, state, error=None, output=None):
        if output is not None and not isinstance(output, str):
            output = json.dumps(output)
        with self._tx() as cur:
            cur.execute(self._q("UPDATE runs SET state = ?, finished_at = ?, error = ?, output = ? WHERE id = ?"),
                        (state, utcnow(), error, output, run_id))

    def get_run(self, run_id):
        with self._tx() as cur:
            cur.execute(self._q("SELECT " + _RUN_COLUMNS + " FROM runs WHERE id = ?"), (run_id,))
            row = cur.fetchone()
        if row is None:
            raise RunNotFound(run_id)
        return _run(row)

    def list_runs(self, job_id):
        with self._tx() as cur:
            cur.execute(self._q("SELECT " + _RUN_COLUMNS + " FROM runs WHERE job_id = ? ORDER BY attempt"), (job_id,))
            return [_run(row) for row in cur.fetchall()]

    def reap_expired_runs(self, now):
        with self._tx() as cur:
            cur.execute(self._q("SELECT id, job_id FROM runs WHERE state = ? AND lease_until < ?"),
                        (RunState.RUNNING, now))
            expired = cur.fetchall()
            for run_id, job_id in expired:
                cur.execute(self._q("UPDATE runs SET state = ?, finished_at = ? WHERE id = ?"),
                            (RunState.LOST, now, run_id))
                cur.execute(self._q("UPDATE jobs SET state = ?, updated_at = ? WHERE id = ? AND state = ?"),
                            (JobState.QUEUED, now, job_id, JobState.RUNNING))
        return len(expired)

    def record_attempt(self, job_id, decision):
        with self._tx() as cur:
            cur.execute(self._q("INSERT INTO job_attempts (job_id, attempt, error, delay_s, next_run_at, recorded_at) "
                                "VALUES (?, ?, ?, ?, ?, ?)"),
                        (job_id, decision.attempt, decision.error, decision.delay, decision.run_at, utcnow()))

    def move_to_dead_letter(self, job_id, reason):
        now = utcnow()
        with self._tx() as cur:
            cur.execute(self._q("UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?"), (JobState.DEAD, now, job_id))
            cur.execute(self._q("INSERT INTO dead_letters (job_id, reason, created_at) VALUES (?, ?, ?)"),
                        (job_id, reason, now))

    def restore_from_dead_letter(self, job_id):
        now = utcnow()
        with self._tx() as cur:
            cur.execute(self._q("DELETE FROM dead_letters WHERE job_id = ?"), (job_id,))
            if cur.rowcount == 0:
                return False
            cur.execute(self._q("UPDATE jobs SET state = ?, attempts = 0, run_at = ?, updated_at = ? WHERE id = ?"),
                        (JobState.QUEUED, now, now, job_id))
        return True

    def list_dead_letters(self, limit=100):
        with self._tx() as cur:
            cur.execute(self._q("SELECT job_id, reason, created_at FROM dead_letters ORDER BY created_at DESC LIMIT ?"),
                        (limit,))
            return [{"job_id": r[0], "reason": r[1], "created_at": ensure_utc(r[2])} for r in cur.fetchall()]

    # payloads --------------------------------------------------------------
    def spill_payload(self, blob):
        ref = new_id("blob")
        with self._tx() as cur:
            cur.execute(self._q("INSERT INTO job_blobs (id, body, size, created_at) VALUES (?, ?, ?, ?)"),
                        (ref, blob, len(blob), utcnow()))
        return ref

    def read_blob(self, ref):
        with self._tx() as cur:
            cur.execute(self._q("SELECT body FROM job_blobs WHERE id = ?"), (ref,))
            row = cur.fetchone()
        if row is None:
            raise KeyError(ref)
        return bytes(row[0])

    # locks, leadership, idempotency ----------------------------------------
    def insert_lock(self, key, owner, expires_at):
        with self._tx() as cur:
            cur.execute(self._q("INSERT INTO job_locks (lock_key, owner, expires_at) VALUES (?, ?, ?) "
                                "ON CONFLICT (lock_key) DO UPDATE SET owner = excluded.owner, "
                                "expires_at = excluded.expires_at WHERE job_locks.expires_at < ?"),
                        (key, owner, expires_at, utcnow()))
            return cur.rowcount == 1

    def extend_lock(self, key, owner, expires_at):
        with self._tx() as cur:
            cur.execute(self._q("UPDATE job_locks SET expires_at = ? WHERE lock_key = ? AND owner = ?"),
                        (expires_at, key, owner))

    def delete_lock(self, key, owner):
        with self._tx() as cur:
            cur.execute(self._q("DELETE FROM job_locks WHERE lock_key = ? AND owner = ?"), (key, owner))

    def try_take_lease(self, node_id, now, ttl):
        with self._tx() as cur:
            cur.execute(self._q("INSERT INTO leader_lease (id, holder, expires_at) VALUES (1, ?, ?) "
                                "ON CONFLICT (id) DO UPDATE SET holder = excluded.holder, "
                                "expires_at = excluded.expires_at "
                                "WHERE leader_lease.holder = excluded.holder OR leader_lease.expires_at < ?"),
                        (node_id, now + timedelta(seconds=ttl), now))
            return cur.rowcount == 1

    def release_lease(self, node_id):
        with self._tx() as cur:
            cur.execute(self._q("UPDATE leader_lease SET expires_at = ? WHERE holder = ?"), (utcnow(), node_id))

    def get_idempotent(self, key, scope):
        with self._tx() as cur:
            cur.execute(self._q("SELECT fingerprint, status, body FROM idempotency_keys "
                                "WHERE idem_key = ? AND scope = ? AND expires_at > ?"), (key, scope, utcnow()))
            row = cur.fetchone()
        return None if row is None else {"fingerprint": row[0], "status": row[1], "body": row[2]}

    def put_idempotent(self, key, scope, fingerprint, status, body, expires_at):
        with self._tx() as cur:
            cur.execute(self._q("INSERT INTO idempotency_keys (idem_key, scope, fingerprint, status, body, expires_at) "
                                "VALUES (?, ?, ?, ?, ?, ?)"), (key, scope, fingerprint, status, body, expires_at))

    def purge_idempotency_keys(self, now):
        with self._tx() as cur:
            cur.execute(self._q("DELETE FROM idempotency_keys WHERE expires_at <= ?"), (now,))
            return cur.rowcount

    # migrations ------------------------------------------------------------
    def migrate(self, dry_run=False):
        with self._tx() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                        "(name TEXT PRIMARY KEY, applied_at TIMESTAMP NOT NULL)")
            cur.execute("SELECT name FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}
        pending = [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in done]
        if not dry_run:
            for path in pending:
                with self._tx() as cur:
                    for statement in split_statements(path.read_text(encoding="utf-8")):
                        cur.execute(statement)
                    cur.execute(self._q("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)"),
                                (path.name, utcnow()))
                log.info("applied migration %s", path.name)
        return [p.name for p in pending]


def split_statements(script):
    lines = [line for line in script.splitlines() if not line.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def _job(row):
    return Job(id=row[0], job_type=row[1], queue=row[2], state=row[3], priority=row[4], run_at=ensure_utc(row[5]),
               attempts=row[6], payload_size=row[7], payload_inline=None if row[8] is None else bytes(row[8]),
               payload_ref=row[9], created_at=ensure_utc(row[10]), updated_at=ensure_utc(row[11]))


def _run(row):
    return Run(id=row[0], job_id=row[1], attempt=row[2], owner=row[3], state=row[4],
               started_at=ensure_utc(row[5]), lease_until=ensure_utc(row[6]), finished_at=ensure_utc(row[7]),
               error=row[8], output=row[9])
