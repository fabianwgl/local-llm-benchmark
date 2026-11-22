"""Leader election over the single-row leader_lease table.

One node at a time holds the lease and runs the periodic duties: promoting
scheduled jobs whose time has come and reaping runs whose worker lease lapsed.
Every node runs workers whether or not it leads.
"""
import logging
import threading
from datetime import timedelta

from tessera.config.env import SINGLE_NODE, flag
from tessera.util.timeutil import utcnow

log = logging.getLogger(__name__)


def lease_expiry(term_start, ttl, skew=0.5):
    """When the holder of a lease taken at `term_start` must consider it lost.

    The holder gives up `skew` seconds before the other nodes may take over, so
    two nodes never both believe they lead.
    """
    return term_start + timedelta(seconds=max(ttl - skew, 0.0))


class LeaderElector:
    def __init__(self, store, node_id, lease_ttl, renew_every, duties=()):
        self._store = store
        self.node_id = node_id
        self.lease_ttl = lease_ttl
        self.renew_every = renew_every
        self._duties = list(duties)
        self._valid_until = None
        self._stop = threading.Event()
        self._thread = None

    @property
    def is_leader(self):
        return self._valid_until is not None and utcnow() < self._valid_until

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="leader", daemon=True)
        self._thread.start()

    def stop(self, timeout=10.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def step(self):
        now = utcnow()
        try:
            won = self._store.try_take_lease(self.node_id, now, self.lease_ttl)
        except Exception:
            log.exception("leader lease renewal failed; stepping down")
            won = False
        if not won:
            if self._valid_until is not None:
                log.info("node %s lost leadership", self.node_id)
            self._valid_until = None
            return
        if not self.is_leader:
            log.info("node %s is now leader", self.node_id)
        self._valid_until = lease_expiry(now, self.lease_ttl)
        run_duties(self._duties)

    def _loop(self):
        while not self._stop.is_set():
            self.step()
            self._stop.wait(self.renew_every)
        if self.is_leader:
            self._store.release_lease(self.node_id)


class StaticElector:
    """Leads unconditionally and runs the duties on a fixed interval."""

    is_leader = True

    def __init__(self, node_id, interval, duties=()):
        self.node_id = node_id
        self.interval = interval
        self._duties = list(duties)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="leader", daemon=True)
        self._thread.start()

    def stop(self, timeout=10.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self):
        while not self._stop.is_set():
            run_duties(self._duties)
            self._stop.wait(self.interval)


def run_duties(duties):
    for duty in duties:
        try:
            duty()
        except Exception:
            log.exception("leader duty %s failed", getattr(duty, "__name__", duty))


def build_elector(leader_cfg, store, node_id, duties=()):
    if flag(SINGLE_NODE):
        log.warning("leader election disabled; node %s leads unconditionally", node_id)
        return StaticElector(node_id, leader_cfg.renew_every, duties)
    return LeaderElector(store, node_id, leader_cfg.lease_ttl, leader_cfg.renew_every, duties)
