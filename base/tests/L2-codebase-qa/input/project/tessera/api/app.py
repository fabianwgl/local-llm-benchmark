"""The WSGI application: router, middleware and per-request context."""
from collections import namedtuple

from tessera.api import admin, routes
from tessera.api.http import Request, Response
from tessera.api.middleware import Idempotency, access_log, error_responses
from tessera.api.router import Router
from tessera.errors import TesseraError

Context = namedtuple("Context", "config store dispatcher elector pool node_id")


def build_router():
    router = Router()
    for method, pattern, handler in routes.ROUTES:
        router.add(method, pattern, handler)
    admin.register(router)
    router.add("GET", "/healthz", healthz)
    return router


def healthz(req, ctx):
    return Response.json(200, {"status": "ok", "node": ctx.node_id, "leader": ctx.elector.is_leader})


class App:
    def __init__(self, cfg, store, dispatcher, elector, pool, node_id):
        self.cfg = cfg
        self.router = build_router()
        self.context = Context(cfg, store, dispatcher, elector, pool, node_id)
        self._idempotency = Idempotency(store, cfg.api.idempotency_header, cfg.api.idempotency_ttl)
        self._pipelines = {}

    def _pipeline(self, route):
        handler = self._pipelines.get((route.method, route.pattern))
        if handler is None:
            handler = access_log(error_responses(self._idempotency.wrap(route.handler)))
            self._pipelines[(route.method, route.pattern)] = handler
        return handler

    def __call__(self, environ, start_response):
        try:
            req = Request.from_environ(environ, self.cfg.api.max_body_bytes)
            route, params = self.router.match(req.method, req.path)
        except TesseraError as exc:
            response = Response.json(exc.status, exc.to_dict())
        else:
            req.params = params
            response = self._pipeline(route)(req, self.context)
        start_response(response.status_line(), list(response.headers.items()))
        return [response.body]


def create_app(cfg, store, dispatcher, elector, pool, node_id):
    return App(cfg, store, dispatcher, elector, pool, node_id)
