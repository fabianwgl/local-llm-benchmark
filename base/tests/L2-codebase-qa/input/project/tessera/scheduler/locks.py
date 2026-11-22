"""Advisory locks on jobs, kept in the job_locks table.

A lock has an owner and an expiry. Once expired it may be taken by anyone, so
holders that run for a long time extend it. Locks are not re-entrant.
"""
import contextlib
import time

from tessera.util.timeutil import lease_expiry, utcnow


class LockTimeout(Exception):
    pass


def job_key(job_id):
    return "job:" + job_id


class JobLock:
    def __init__(self, manager, key, owner, expires_at):
        self.manager = manager
        self.key = key
        self.owner = owner
        self.expires_at = expires_at
        self.released = False

    def extend(self, ttl):
        self.expires_at = lease_expiry(utcnow(), ttl)
        self.manager.store.extend_lock(self.key, self.owner, self.expires_at)

    def release(self):
        if not self.released:
            self.manager.store.delete_lock(self.key, self.owner)
            self.released = True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.release()
        return False


class LockManager:
    def __init__(self, store, default_ttl=60.0, poll_interval=0.05):
        self.store = store
        self.default_ttl = default_ttl
        self.poll_interval = poll_interval

    def try_acquire(self, key, owner, ttl=None):
        """The lock, or None if somebody else holds an unexpired lock on `key`."""
        expires_at = lease_expiry(utcnow(), ttl or self.default_ttl)
        if self.store.insert_lock(key, owner, expires_at):
            return JobLock(self, key, owner, expires_at)
        return None

    def acquire(self, key, owner, timeout, ttl=None):
        """Wait up to `timeout` seconds for the lock; raises LockTimeout."""
        deadline = time.monotonic() + timeout
        while True:
            lock = self.try_acquire(key, owner, ttl)
            if lock is not None:
                return lock
            if time.monotonic() >= deadline:
                raise LockTimeout(key)
            time.sleep(self.poll_interval)

    @contextlib.contextmanager
    def hold(self, key, owner, timeout, ttl=None):
        lock = self.acquire(key, owner, timeout, ttl)
        try:
            yield lock
        finally:
            lock.release()
