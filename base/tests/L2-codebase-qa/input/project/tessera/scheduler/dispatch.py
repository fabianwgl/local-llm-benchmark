"""Moving jobs through their states: claim, complete, requeue, cancel, pause, resume, revive."""
import logging

from tessera.errors import InvalidTransition, JobNotFound
from tessera.models import TERMINAL_STATES, JobState, RunState
from tessera.scheduler.locks import job_key

log = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, store, locks, lock_timeout=5.0):
        self._store = store
        self._locks = locks
        self._lock_timeout = lock_timeout

    def claim_next(self, queues, owner, lease_until):
        """Claim the next runnable job from `queues`. Returns (job, run, lock) or None."""
        for job in self._store.runnable_jobs(queues, limit=10):
            lock = self._locks.try_acquire(job_key(job.id), owner)
            if lock is None:
                continue
            try:
                run = self._store.start_run(job.id, owner, lease_until)
            except BaseException:
                lock.release()
                raise
            if run is None:
                lock.release()
                continue
            return job, run, lock
        return None

    def complete(self, job, run, output):
        self._store.finish_run(run.id, RunState.SUCCEEDED, output=output)
        self._store.set_state(job.id, JobState.SUCCEEDED)

    def requeue(self, job, run, decision):
        """Record a failed run, then schedule the next attempt or dead-letter the job."""
        self._store.finish_run(run.id, RunState.FAILED, error=decision.error)
        self._store.record_attempt(job.id, decision)
        if decision.retry:
            self._store.reschedule(job.id, decision.run_at)
            log.info("job %s attempt %d failed; next attempt in %.1fs", job.id, decision.attempt, decision.delay)
        else:
            self._store.move_to_dead_letter(job.id, decision.error)
            log.warning("job %s dead-lettered after attempt %d", job.id, decision.attempt)

    def cancel(self, job_id, actor):
        with self._locks.hold(job_key(job_id), actor, self._lock_timeout):
            job = self._store.get_job(job_id)
            if job.state in TERMINAL_STATES:
                raise InvalidTransition(job.state, JobState.CANCELLED)
            self._store.set_state(job_id, JobState.CANCELLED)
            return self._store.get_job(job_id)

    def pause(self, job_id, actor):
        lock = self._locks.acquire(job_key(job_id), actor, self._lock_timeout)
        job = self._store.get_job(job_id)
        try:
            if job.state not in (JobState.QUEUED, JobState.SCHEDULED):
                raise InvalidTransition(job.state, JobState.PAUSED)
            self._store.set_state(job_id, JobState.PAUSED)
            return self._store.get_job(job_id)
        finally:
            lock.release()

    def resume(self, job_id, actor):
        with self._locks.hold(job_key(job_id), actor, self._lock_timeout):
            job = self._store.get_job(job_id)
            if job.state != JobState.PAUSED:
                raise InvalidTransition(job.state, JobState.QUEUED)
            self._store.set_state(job_id, JobState.QUEUED)
            return self._store.get_job(job_id)

    def run_now(self, job_id, actor, now):
        with self._locks.hold(job_key(job_id), actor, self._lock_timeout):
            job = self._store.get_job(job_id)
            if job.state not in (JobState.QUEUED, JobState.SCHEDULED):
                raise InvalidTransition(job.state, JobState.QUEUED)
            self._store.reschedule(job_id, now)
            return self._store.get_job(job_id)

    def revive(self, job_id, actor):
        """Move a dead-lettered job back to its queue with a fresh attempt budget."""
        with self._locks.hold(job_key(job_id), actor, self._lock_timeout):
            if not self._store.restore_from_dead_letter(job_id):
                raise JobNotFound(job_id)
            return self._store.get_job(job_id)
