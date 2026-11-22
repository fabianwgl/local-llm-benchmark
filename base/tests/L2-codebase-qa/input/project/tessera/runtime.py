"""Wires the components of one node together."""
import logging
import socket
import threading
from wsgiref.simple_server import WSGIRequestHandler, make_server

from tessera.api.app import create_app
from tessera.scheduler import Dispatcher, LockManager, RetryPlanner, build_elector
from tessera.storage import open_store
from tessera.util.timeutil import utcnow
from tessera.worker import WorkerPool, default_registry

log = logging.getLogger(__name__)


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, fmt, *args):
        log.debug("http: " + fmt, *args)


class Runtime:
    def __init__(self, cfg, store, elector, pool, app):
        self.cfg = cfg
        self.store = store
        self.elector = elector
        self.pool = pool
        self.app = app
        self._http = None

    def start(self, api=True):
        self.elector.start()
        self.pool.start()
        if api:
            self._http = make_server(self.cfg.api.host, self.cfg.api.port, self.app, handler_class=_QuietHandler)
            threading.Thread(target=self._http.serve_forever, name="http", daemon=True).start()
            log.info("listening on %s:%d", self.cfg.api.host, self.cfg.api.port)

    def shutdown(self):
        if self._http is not None:
            self._http.shutdown()
        self.pool.stop()
        self.elector.stop()
        self.store.close()


def build_runtime(cfg, registry=None):
    node_id = cfg.node.id or socket.gethostname()
    store = open_store(cfg.storage)
    locks = LockManager(store, default_ttl=cfg.worker.lease_ttl)
    dispatcher = Dispatcher(store, locks)
    planner = RetryPlanner(cfg.retry)
    duties = [
        lambda: store.promote_due(utcnow()),
        lambda: store.reap_expired_runs(utcnow()),
        lambda: store.purge_idempotency_keys(utcnow()),
    ]
    elector = build_elector(cfg.leader, store, node_id, duties)
    pool = WorkerPool(cfg.worker, store, dispatcher, planner, registry or default_registry, node_id)
    app = create_app(cfg, store, dispatcher, elector, pool, node_id)
    return Runtime(cfg, store, elector, pool, app)
