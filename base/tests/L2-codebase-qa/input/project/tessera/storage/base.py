"""The interface every storage backend implements."""


class Store:
    """Persistent state of the scheduler. Methods are safe to call from several threads."""

    # jobs
    def insert_job(self, spec, stored_payload):
        """Create a job and return it. `stored_payload` comes from tessera.payload.prepare_payload."""
        raise NotImplementedError

    def get_job(self, job_id):
        """Return the job. Raises JobNotFound if there is none."""
        raise NotImplementedError

    def list_jobs(self, state=None, queue=None, limit=100, after=None):
        raise NotImplementedError

    def set_state(self, job_id, state):
        raise NotImplementedError

    def reschedule(self, job_id, run_at):
        """Put the job back in the scheduled state, due at `run_at`."""
        raise NotImplementedError

    def runnable_jobs(self, queues, limit):
        """Queued jobs in `queues`, highest priority first, then oldest first."""
        raise NotImplementedError

    def promote_due(self, now):
        """Move scheduled jobs whose run_at has passed to the queued state."""
        raise NotImplementedError

    # runs and attempts
    def start_run(self, job_id, owner, lease_until):
        """Start the next attempt of a queued job. None if the job is no longer queued."""
        raise NotImplementedError

    def finish_run(self, run_id, state, error=None, output=None):
        raise NotImplementedError

    def get_run(self, run_id):
        raise NotImplementedError

    def list_runs(self, job_id):
        raise NotImplementedError

    def reap_expired_runs(self, now):
        """Mark runs whose lease lapsed as lost and requeue their jobs."""
        raise NotImplementedError

    def record_attempt(self, job_id, decision):
        """Persist the outcome of a failed attempt (a scheduler.retry.RetryDecision)."""
        raise NotImplementedError

    def move_to_dead_letter(self, job_id, reason):
        raise NotImplementedError

    def restore_from_dead_letter(self, job_id):
        raise NotImplementedError

    def list_dead_letters(self, limit=100):
        raise NotImplementedError

    # payloads
    def spill_payload(self, blob):
        """Store an oversized payload out of line and return its reference."""
        raise NotImplementedError

    def read_blob(self, ref):
        raise NotImplementedError

    # locks, leadership, idempotency
    def insert_lock(self, key, owner, expires_at):
        """Take the lock if it is free or expired. Returns True on success."""
        raise NotImplementedError

    def extend_lock(self, key, owner, expires_at):
        raise NotImplementedError

    def delete_lock(self, key, owner):
        raise NotImplementedError

    def try_take_lease(self, node_id, now, ttl):
        raise NotImplementedError

    def release_lease(self, node_id):
        raise NotImplementedError

    def get_idempotent(self, key, scope):
        raise NotImplementedError

    def put_idempotent(self, key, scope, fingerprint, status, body, expires_at):
        raise NotImplementedError

    def purge_idempotency_keys(self, now):
        raise NotImplementedError

    # maintenance
    def migrate(self, dry_run=False):
        raise NotImplementedError

    def close(self):
        pass
