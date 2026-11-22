"""Worker threads: claim a job, run its handler, report the outcome."""
import logging
import threading

from tessera.errors import UnknownJobType
from tessera.payload import load_payload
from tessera.scheduler import lease_expiry
from tessera.util.timeutil import utcnow

log = logging.getLogger(__name__)


class JobRegistry:
    """Maps job types to callables that take the decoded payload and return a JSON-able result."""

    def __init__(self):
        self._handlers = {}

    def register(self, job_type, fn=None):
        if fn is None:
            return lambda f: self.register(job_type, f)
        if job_type in self._handlers:
            raise ValueError("job type %r is already registered" % job_type)
        self._handlers[job_type] = fn
        return fn

    def get(self, job_type):
        try:
            return self._handlers[job_type]
        except KeyError:
            raise UnknownJobType("no handler registered for job type %r" % job_type) from None

    def types(self):
        return sorted(self._handlers)


default_registry = JobRegistry()


class Worker:
    def __init__(self, name, store, dispatcher, planner, registry, queues, lease_ttl, poll_interval):
        self.name = name
        self.store = store
        self.dispatcher = dispatcher
        self.planner = planner
        self.registry = registry
        self.queues = list(queues)
        self.lease_ttl = lease_ttl
        self.poll_interval = poll_interval

    def run(self, stop):
        while not stop.is_set():
            try:
                busy = self.poll_once()
            except Exception:
                log.exception("worker %s: poll failed", self.name)
                busy = False
            if not busy:
                stop.wait(self.poll_interval)

    def poll_once(self):
        """Run at most one job. Returns True if a job was claimed."""
        claimed = self.dispatcher.claim_next(self.queues, self.name, lease_expiry(utcnow(), self.lease_ttl))
        if claimed is None:
            return False
        job, run, lock = claimed
        try:
            self._execute(job, run)
        finally:
            lock.release()
        return True

    def _execute(self, job, run):
        log.debug("worker %s: job %s (%s) attempt %d", self.name, job.id, job.job_type, run.attempt)
        try:
            handler = self.registry.get(job.job_type)
            output = handler(load_payload(job, self.store))
        except Exception as exc:
            decision = self.planner.decide(job, run.attempt, exc)
            self.dispatcher.requeue(job, run, decision)
            return
        self.dispatcher.complete(job, run, output)


class WorkerPool:
    def __init__(self, worker_cfg, store, dispatcher, planner, registry, node_id):
        self.workers = [
            Worker("%s/w%d" % (node_id, i), store, dispatcher, planner, registry,
                   worker_cfg.queues, worker_cfg.lease_ttl, worker_cfg.poll_interval)
            for i in range(worker_cfg.concurrency)
        ]
        self._stop = threading.Event()
        self._threads = []
        self.draining = False

    def start(self):
        for worker in self.workers:
            t = threading.Thread(target=worker.run, args=(self._stop,), name=worker.name, daemon=True)
            t.start()
            self._threads.append(t)

    def drain(self):
        """Stop claiming new jobs; jobs already running finish normally."""
        self.draining = True
        self._stop.set()

    def stop(self, timeout=30.0):
        self._stop.set()
        for t in self._threads:
            t.join(timeout)
