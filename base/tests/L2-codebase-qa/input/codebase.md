# Repository dump: tessera
Every file of the repository follows, under a heading with its path.

## README.md

````markdown
# tessera

tessera is a small job scheduler for services that need durable background work
without running a separate broker. Jobs live in PostgreSQL (or SQLite for
development), every node runs workers, and one elected node performs the
periodic housekeeping.

## Features

- HTTP API for submitting, inspecting, pausing and cancelling jobs
- per-job-type retry policies with exponential backoff
- dead-letter handling and manual requeue
- idempotent POST requests (a repeated request replays the first response)
- out-of-line storage for large payloads
- a TypeScript client in `clients/ts`

## Quick start

```sh
pip install -e '.[postgres]'
tessera migrate --config config/tessera.yaml
tessera serve --config config/tessera.yaml
```

Submit a job:

```sh
curl -s -X POST localhost:8740/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"type": "email.send", "payload": {"to": "ops@example.com", "template": "digest"}}'
```

## Writing job handlers

Handlers are plain functions registered for a job type. They receive the
decoded payload and return a JSON-serialisable result. Raising any exception
fails the attempt; raise `tessera.errors.PermanentError` to skip the remaining
retries.

```python
from tessera.worker import default_registry

@default_registry.register("email.send")
def send_email(payload):
    ...
```

## Configuration

Settings are layered. Built-in defaults (`tessera/config/defaults.py`) are
overridden by the YAML file, which is overridden by environment variables,
which are overridden by command-line flags. `tessera show-config` prints the
result. Durations accept `90s`, `5m` or `1h30m`; sizes accept `64KiB` or `2MB`.

Retry settings under `retry` apply to every job type; entries under
`retry.policies` adjust them for individual job types.

The environment variables tessera understands are defined in
`tessera/config/env.py`.

## Development

```sh
pip install -e '.[dev]'
pytest
```

The SQLite backend needs no setup: point `storage.url` at
`sqlite:///tmp/tessera.db` and run `tessera migrate` once.

See `docs/architecture.md` for how the pieces fit together.
````

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "tessera"
version = "0.14.2"
description = "A small, durable job scheduler backed by PostgreSQL or SQLite"
requires-python = ">=3.9"
dependencies = ["pyyaml>=6.0"]

[project.optional-dependencies]
postgres = ["psycopg2-binary>=2.9"]
dev = ["pytest>=7", "ruff>=0.4"]

[project.scripts]
tessera = "tessera.cli:main"

[tool.setuptools.packages.find]
include = ["tessera*"]

[tool.ruff]
line-length = 110

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## docs/architecture.md

```markdown
# Architecture

This note describes how a tessera node is put together and how a job moves
through it. It is meant for people changing tessera, not for operators.

## Components

A node is one process (`tessera serve`) containing:

- **API**: a WSGI app (`tessera/api`). Requests pass through access logging,
  error mapping and idempotent replay before reaching a handler. Handlers
  are thin; state changes go through the dispatcher or the store.
- **Dispatcher** (`tessera/scheduler/dispatch.py`): the only code that moves
  jobs between states. Operations that race with workers take the job's lock.
- **Workers** (`tessera/worker.py`): `worker.concurrency` threads that poll the
  queues listed in `worker.queues`, claim a job, run its handler and report the
  outcome back to the dispatcher.
- **Retry planner** (`tessera/scheduler/retry.py`): turns a failed attempt into
  a decision: try again at a given time, or give up.
- **Leader elector** (`tessera/scheduler/leader.py`): keeps a lease in the
  database. The leader promotes scheduled jobs that are due, reaps runs whose
  worker vanished and purges expired idempotency keys.
- **Store** (`tessera/storage`): all persistent state. The SQL is shared between
  PostgreSQL and SQLite; each backend adds what its database needs.

## Life of a job

1. `POST /v1/jobs` validates the body, encodes the payload and inserts the job
   as `queued` (or `scheduled` if `run_at` is in the future).
2. A worker claims it: the job's lock is taken, the job moves to `running` and a
   run row is created with the next attempt number and a lease.
3. The handler runs. On success the run and the job are marked succeeded.
4. On failure the attempt is recorded and the job is either rescheduled after
   a backoff delay or moved to the dead-letter list.
5. The leader moves due `scheduled` jobs back to `queued`.

Runs whose lease lapses (the worker crashed or lost the database) are marked
`lost` and their job is queued again; the attempt counter is not reset.

## Locks and leases

Job locks are rows in `job_locks` with an owner and an expiry. They exist so
that pause, resume and cancel cannot interleave with a worker reporting a result.

Leadership is a single-row lease that the holder renews every
`leader.renew_every`. A holder that cannot renew steps down before the lease
expires for the others. For local development a node can be told to skip
election and lead unconditionally.

## Payload size

Payloads are stored inline in the job row up to `jobs.max_payload_bytes`.
What happens above that is decided by `jobs.payload_overflow`. Separately, the
API refuses request bodies larger than `api.max_body_bytes` before parsing them.

## Configuration

See `tessera/config/loader.py` for the precedence rules and the legacy key
names that are still accepted.
```

## config/tessera.yaml

```yaml
# tessera production configuration.
# Keys not listed here keep their built-in defaults (tessera/config/defaults.py).

node:
  data_dir: /srv/tessera

api:
  port: 8740
  max_body_bytes: 2MiB
  idempotency_header: X-Tessera-Idem-Key
  idempotency_ttl: 48h

jobs:
  max_payload_bytes: 64KiB
  payload_overflow: spill
  max_runtime: 30m

retry:
  max_attempts: 6
  base_delay: 5s
  max_delay: 10m
  policies:
    report.render:
      base_delay: 15s
      factor: 3
    email.send:
      base_delay: 1s
      max_delay: 1m
      max_attempts: 10
    billing.charge:
      max_attempts: 3
      multiplier: 4

worker:
  concurrency: 8
  queues: [default, reports, mail]
  lease_ttl: 90s

leader:
  lease_ttl: 20s
  renew_every: 5s

storage:
  url: postgresql://tessera@db.internal:5432/tessera
  pool_size: 20

logging:
  format: json
```

## tessera/__init__.py

```python
"""tessera: a small, durable job scheduler.

See README.md for an overview and docs/architecture.md for the moving parts.
"""

__version__ = "0.14.2"
```

## tessera/api/__init__.py

```python
"""HTTP API (WSGI)."""
```

## tessera/api/admin.py

```python
"""Operator endpoints under /v1/admin."""
from tessera.api import jobs
from tessera.api.http import Response
from tessera.scheduler.backoff import schedule
from tessera.scheduler.retry import RetryPolicy
from tessera.util.timeutil import isoformat


def register(router):
    router.add("GET", "/v1/admin/leader", leader_status)
    router.add("GET", "/v1/admin/dead-letters", list_dead_letters)
    router.add("POST", "/v1/admin/jobs/{job_id}/requeue", jobs.requeue_job)
    router.add("POST", "/v1/admin/drain", drain)
    router.add("GET", "/v1/admin/retry-policies", retry_policies)


def leader_status(req, ctx):
    return Response.json(200, {"node": ctx.node_id, "leader": ctx.elector.is_leader})


def list_dead_letters(req, ctx):
    items = ctx.store.list_dead_letters(limit=200)
    return Response.json(200, {"items": [
        {"job_id": i["job_id"], "reason": i["reason"], "created_at": isoformat(i["created_at"])} for i in items
    ]})


def drain(req, ctx):
    ctx.pool.drain()
    return Response.json(202, {"node": ctx.node_id, "draining": True})


def retry_policies(req, ctx):
    retry = ctx.config.retry
    out = {}
    for name in ["*"] + sorted(retry.policies.as_dict()):
        policy = RetryPolicy.resolve(retry, name)
        out[name] = {
            "max_attempts": policy.max_attempts,
            "delays": schedule(policy.base_delay, policy.multiplier, policy.max_delay, policy.max_attempts),
        }
    return Response.json(200, out)
```

## tessera/api/app.py

```python
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
```

## tessera/api/http.py

```python
"""Request and response objects for the WSGI application."""
import json
from http import HTTPStatus
from urllib.parse import parse_qs

from tessera.errors import RequestTooLarge, ValidationError


class Request:
    def __init__(self, method, path, headers, body, query):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.query = query
        self.params = {}

    @classmethod
    def from_environ(cls, environ, max_body):
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length > max_body:
            raise RequestTooLarge("request body is %d bytes; the limit is %d" % (length, max_body))
        body = environ["wsgi.input"].read(length) if length else b""
        headers = {k[5:].replace("_", "-").title(): v for k, v in environ.items() if k.startswith("HTTP_")}
        if environ.get("CONTENT_TYPE"):
            headers["Content-Type"] = environ["CONTENT_TYPE"]
        query = {k: v[-1] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}
        return cls(environ["REQUEST_METHOD"].upper(), environ.get("PATH_INFO") or "/", headers, body, query)

    def header(self, name, default=None):
        return self.headers.get(name.title(), default)

    def json(self):
        if not self.body:
            raise ValidationError("request body is empty")
        try:
            return json.loads(self.body)
        except ValueError:
            raise ValidationError("request body is not valid JSON") from None


class Response:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self.body = body
        self.headers = dict(headers or {})

    @classmethod
    def json(cls, status, obj):
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return cls(status, body, {"Content-Type": "application/json"})

    @classmethod
    def empty(cls, status=204):
        return cls(status)

    def status_line(self):
        return "%d %s" % (self.status, HTTPStatus(self.status).phrase)
```

## tessera/api/jobs.py

```python
"""Handlers for /v1/jobs."""
from tessera.api.http import Response
from tessera.errors import ValidationError
from tessera.models import JobSpec
from tessera.payload import prepare_payload

MAX_PAGE = 500


def create_job(req, ctx):
    spec = JobSpec.from_dict(req.json(), ctx.config.jobs.default_queue)
    stored = prepare_payload(spec.payload, ctx.config.jobs, ctx.store)
    job = ctx.store.insert_job(spec, stored)
    return Response.json(201, job.to_dict())


def list_jobs(req, ctx):
    limit = _limit(req)
    jobs = ctx.store.list_jobs(state=req.query.get("state"), queue=req.query.get("queue"),
                               limit=limit, after=req.query.get("after"))
    cursor = jobs[-1].id if len(jobs) == limit else None
    return Response.json(200, {"items": [job.to_dict() for job in jobs], "next": cursor})


def get_job(req, ctx):
    return Response.json(200, ctx.store.get_job(req.params["job_id"]).to_dict())


def cancel_job(req, ctx):
    job = ctx.dispatcher.cancel(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def pause_job(req, ctx):
    job = ctx.dispatcher.pause(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def resume_job(req, ctx):
    job = ctx.dispatcher.resume(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def requeue_job(req, ctx):
    job = ctx.dispatcher.revive(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def actor(req):
    return "api:" + (req.header("X-Tessera-Client") or "anonymous")


def _limit(req):
    raw = req.query.get("limit", "100")
    try:
        limit = int(raw)
    except ValueError:
        raise ValidationError("'limit' must be an integer") from None
    if not 1 <= limit <= MAX_PAGE:
        raise ValidationError("'limit' must be between 1 and %d" % MAX_PAGE)
    return limit
```

## tessera/api/middleware.py

```python
"""Stages wrapped around every handler: access log, error mapping, idempotent replay."""
import hashlib
import logging
import time
from datetime import timedelta

from tessera.api.http import Response
from tessera.errors import Busy, IdempotencyConflict, TesseraError
from tessera.scheduler.locks import LockTimeout
from tessera.util.timeutil import utcnow

log = logging.getLogger("tessera.api")


class Idempotency:
    """Replays the stored response when a POST is repeated with the same key and body."""

    def __init__(self, store, header, ttl):
        self.store = store
        self.header = header
        self.ttl = ttl

    def wrap(self, handler):
        def idempotent(req, ctx):
            key = req.header(self.header) if req.method == "POST" else None
            if not key:
                return handler(req, ctx)
            scope = req.method + " " + req.path
            fingerprint = hashlib.sha256(req.body).hexdigest()
            seen = self.store.get_idempotent(key, scope)
            if seen is not None:
                if seen["fingerprint"] != fingerprint:
                    raise IdempotencyConflict("key %r was already used with a different body" % key)
                return Response(seen["status"], bytes(seen["body"]),
                                {"Content-Type": "application/json", "Idempotent-Replay": "true"})
            response = handler(req, ctx)
            if response.status < 500:
                self.store.put_idempotent(key, scope, fingerprint, response.status, response.body,
                                          utcnow() + timedelta(seconds=self.ttl))
            return response

        return idempotent


def error_responses(handler):
    def guarded(req, ctx):
        try:
            return handler(req, ctx)
        except LockTimeout:
            return _error(Busy("the job is locked by another operation; try again"))
        except TesseraError as exc:
            return _error(exc)
        except Exception:
            log.exception("unhandled error in %s %s", req.method, req.path)
            return _error(TesseraError("internal error"))

    return guarded


def access_log(handler):
    def logged(req, ctx):
        started = time.monotonic()
        response = handler(req, ctx)
        log.info("%s %s %d %.1fms", req.method, req.path, response.status, (time.monotonic() - started) * 1000)
        return response

    return logged


def _error(exc):
    return Response.json(exc.status, exc.to_dict())
```

## tessera/api/router.py

```python
"""Method and path routing with {name} path parameters."""
import re
from collections import namedtuple

from tessera.errors import MethodNotAllowed, RouteNotFound

Route = namedtuple("Route", "method pattern regex handler")

_PARAM = re.compile(r"\{([a-z_]+)\}")


class Router:
    def __init__(self):
        self._routes = []

    def add(self, method, pattern, handler):
        method = method.upper()
        for route in self._routes:
            if route.method == method and route.pattern == pattern:
                raise ValueError("duplicate route %s %s" % (method, pattern))
        regex = re.compile("^" + _PARAM.sub(r"(?P<\1>[^/]+)", pattern) + "$")
        self._routes.append(Route(method, pattern, regex, handler))

    def match(self, method, path):
        """(route, path parameters) for the request; raises RouteNotFound or MethodNotAllowed."""
        allowed = set()
        for route in self._routes:
            m = route.regex.match(path)
            if m is None:
                continue
            if route.method == method:
                return route, m.groupdict()
            allowed.add(route.method)
        if allowed:
            raise MethodNotAllowed("allowed: " + ", ".join(sorted(allowed)))
        raise RouteNotFound(path)

    def routes(self):
        return [(r.method, r.pattern, r.handler) for r in self._routes]
```

## tessera/api/routes.py

```python
"""Routes of the public API."""
from tessera.api import jobs, runs

ROUTES = [
    ("POST", "/v1/jobs", jobs.create_job),
    ("GET", "/v1/jobs", jobs.list_jobs),
    ("GET", "/v1/jobs/{job_id}", jobs.get_job),
    ("POST", "/v1/jobs/{job_id}/cancel", jobs.cancel_job),
    ("POST", "/v1/jobs/{job_id}/pause", jobs.pause_job),
    ("POST", "/v1/jobs/{job_id}/resume", jobs.resume_job),
    ("GET", "/v1/jobs/{job_id}/runs", runs.list_runs),
    ("POST", "/v1/jobs/{job_id}/runs", runs.start_run),
    ("GET", "/v1/runs/{run_id}", runs.get_run),
]
```

## tessera/api/runs.py

```python
"""Handlers for runs."""
from tessera.api.http import Response
from tessera.api.jobs import actor
from tessera.util.timeutil import utcnow


def list_runs(req, ctx):
    job_id = req.params["job_id"]
    ctx.store.get_job(job_id)
    return Response.json(200, {"items": [run.to_dict() for run in ctx.store.list_runs(job_id)]})


def start_run(req, ctx):
    job = ctx.dispatcher.run_now(req.params["job_id"], actor(req), utcnow())
    return Response.json(202, job.to_dict())


def get_run(req, ctx):
    return Response.json(200, ctx.store.get_run(req.params["run_id"]).to_dict())


def get_run_output(req, ctx):
    run = ctx.store.get_run(req.params["run_id"])
    if run.output is None:
        return Response.empty(204)
    return Response(200, run.output.encode("utf-8"), {"Content-Type": "application/json"})
```

## tessera/cli.py

```python
"""Command-line entry point (`tessera <command>`)."""
import argparse
import json
import logging
import signal
import sys
import threading

from tessera import __version__
from tessera.config import ConfigError, load_config

log = logging.getLogger("tessera")

# argparse dest -> dotted configuration key
FLAG_KEYS = {
    "port": "api.port",
    "concurrency": "worker.concurrency",
    "queues": "worker.queues",
    "max_backoff": "retry.max_delay",
    "log_level": "logging.level",
}


def build_parser():
    parser = argparse.ArgumentParser(prog="tessera", description="durable job scheduler")
    parser.add_argument("--version", action="version", version="tessera " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the API, the workers and leader election")
    _common(serve)
    serve.add_argument("--port", type=int, help="HTTP port (api.port)")
    serve.add_argument("--concurrency", type=int, help="worker threads (worker.concurrency)")
    serve.add_argument("--queues", help="comma-separated queues to consume (worker.queues)")
    serve.add_argument("--max-backoff", metavar="DURATION",
                       help="upper bound for retry delays, e.g. 90s or 5m (retry.max_delay)")
    serve.add_argument("--no-api", action="store_true", help="run workers only")

    migrate = sub.add_parser("migrate", help="apply pending SQL migrations and exit")
    _common(migrate)
    migrate.add_argument("--dry-run", action="store_true", help="list pending migrations only")

    show = sub.add_parser("show-config", help="print the effective configuration as JSON")
    _common(show)
    return parser


def _common(parser):
    parser.add_argument("--config", metavar="PATH",
                        help="YAML file (default: $TESSERA_CONFIG, then /etc/tessera/tessera.yaml)")
    parser.add_argument("--log-level", help="DEBUG, INFO, WARNING or ERROR (logging.level)")


def flag_overrides(args):
    found = {}
    for dest, key in FLAG_KEYS.items():
        value = getattr(args, dest, None)
        if value is not None:
            found[key] = value
    return found


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config, cli=flag_overrides(args))
    except ConfigError as exc:
        print("tessera: %s" % exc, file=sys.stderr)
        return 2
    logging.basicConfig(level=cfg.logging.level, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if args.command == "show-config":
        print(json.dumps(cfg.as_dict(), indent=2, sort_keys=True, default=str))
        return 0
    if args.command == "migrate":
        from tessera.storage import migrate

        for name in migrate(cfg.storage, dry_run=args.dry_run):
            print(("pending " if args.dry_run else "applied ") + name)
        return 0
    return serve(cfg, api=not args.no_api)


def serve(cfg, api=True):
    from tessera.runtime import build_runtime

    runtime = build_runtime(cfg)
    stop = threading.Event()

    def _on_signal(signum, frame):
        log.info("signal %d received, shutting down", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    runtime.start(api=api)
    stop.wait()
    runtime.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## tessera/config/__init__.py

```python
"""Configuration: built-in defaults, tessera.yaml, environment, command line."""
from tessera.config.loader import Config, ConfigError, load_config

__all__ = ["Config", "ConfigError", "load_config"]
```

## tessera/config/defaults.py

```python
"""Built-in configuration defaults.

Every key the service reads has a default here. The loader rejects unknown
top-level sections, so a misspelt section in tessera.yaml fails at startup
instead of being silently ignored.

Durations may be written as numbers of seconds or as strings such as "90s",
"5m" or "1h30m"; sizes as bytes or as strings such as "64KiB" or "2MB".
"""

DEFAULTS = {
    "node": {
        "id": None,
        "data_dir": "/var/lib/tessera",
    },
    "api": {
        "host": "0.0.0.0",
        "port": 8740,
        "max_body_bytes": "1MiB",
        "idempotency_header": "Idempotency-Key",
        "idempotency_ttl": "24h",
        "request_timeout": "30s",
    },
    "jobs": {
        "max_payload_bytes": "256KiB",
        "payload_overflow": "reject",
        "default_queue": "default",
        "max_runtime": "15m",
    },
    "retry": {
        "max_attempts": 5,
        "base_delay": "2s",
        "multiplier": 2.0,
        "max_delay": "5m",
        "policies": {},
    },
    "worker": {
        "concurrency": 4,
        "queues": ["default"],
        "poll_interval": "1s",
        "lease_ttl": "60s",
    },
    "leader": {
        "lease_ttl": "15s",
        "renew_every": "5s",
    },
    "storage": {
        "url": "sqlite:///var/lib/tessera/tessera.db",
        "pool_size": 5,
        "statement_timeout": "10s",
    },
    "logging": {
        "level": "INFO",
        "format": "text",
    },
}
```

## tessera/config/env.py

```python
"""Environment variables read by tessera.

Most variables override one configuration key and are listed in OVERRIDES; the
loader applies them on top of the YAML file. A few switches are not part of the
configuration tree and are read with flag() by the component that needs them.
"""
import os

CONFIG_FILE = "TESSERA_CONFIG"
NODE_ID = "TESSERA_NODE_ID"
LOG_LEVEL = "TESSERA_LOG_LEVEL"
STORAGE_URL = "TESSERA_STORAGE_URL"
SINGLE_NODE = "TESSERA_SOLO_MODE"
DEBUG_SQL = "TESSERA_DEBUG_SQL"

OVERRIDES = {
    NODE_ID: "node.id",
    LOG_LEVEL: "logging.level",
    STORAGE_URL: "storage.url",
    "TESSERA_API_PORT": "api.port",
    "TESSERA_WORKER_CONCURRENCY": "worker.concurrency",
    "TESSERA_WORKER_QUEUES": "worker.queues",
    "TESSERA_RETRY_MAX_ATTEMPTS": "retry.max_attempts",
    "TESSERA_RETRY_BASE_DELAY": "retry.base_delay",
    "TESSERA_RETRY_MAX_DELAY": "retry.max_delay",
}

_TRUE = frozenset(["1", "true", "yes", "on"])


def flag(name, environ=None):
    """True if the variable is set to "1", "true", "yes" or "on" (any case)."""
    environ = os.environ if environ is None else environ
    return environ.get(name, "").strip().lower() in _TRUE


def overrides(environ=None):
    """{dotted config key: raw string} for every variable in OVERRIDES that is set and non-empty."""
    environ = os.environ if environ is None else environ
    found = {}
    for var, key in OVERRIDES.items():
        value = environ.get(var)
        if value is not None and value.strip() != "":
            found[key] = value.strip()
    return found
```

## tessera/config/loader.py

```python
"""Layered configuration.

Layers, lowest precedence first:

1. tessera.config.defaults.DEFAULTS
2. the YAML file (--config, else $TESSERA_CONFIG, else /etc/tessera/tessera.yaml)
3. environment variables listed in tessera.config.env.OVERRIDES
4. command-line flags (see tessera.cli)

Mappings from the YAML file are merged key by key into the defaults; every
other value replaces the one below it. Environment variables and flags each
set a single key. After merging, durations become float seconds and sizes
become int bytes.
"""
import copy
import os

from tessera.config import env
from tessera.config.defaults import DEFAULTS
from tessera.util import parse_duration, parse_size

DEFAULT_PATH = "/etc/tessera/tessera.yaml"

DURATION_KEYS = frozenset([
    "api.idempotency_ttl", "api.request_timeout", "jobs.max_runtime",
    "retry.base_delay", "retry.max_delay", "worker.poll_interval", "worker.lease_ttl",
    "leader.lease_ttl", "leader.renew_every", "storage.statement_timeout",
])
SIZE_KEYS = frozenset(["api.max_body_bytes", "jobs.max_payload_bytes"])
INT_KEYS = frozenset(["api.port", "worker.concurrency", "retry.max_attempts", "storage.pool_size"])
FLOAT_KEYS = frozenset(["retry.multiplier"])
LIST_KEYS = frozenset(["worker.queues"])
CHOICES = {
    "jobs.payload_overflow": ("reject", "spill"),
    "logging.format": ("text", "json"),
}

# Keys renamed since 0.9. The old spellings are still accepted in YAML files.
RENAMED = {
    "storage.dsn": "storage.url",
    "jobs.max_payload": "jobs.max_payload_bytes",
    "retry.factor": "retry.multiplier",
    "retry.cap": "retry.max_delay",
}

POLICY_FIELDS = ("max_attempts", "base_delay", "multiplier", "max_delay")


class ConfigError(Exception):
    pass


class Config:
    """Read-only attribute view over the merged configuration tree."""

    def __init__(self, data, path=""):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, name):
        try:
            value = self._data[name]
        except KeyError:
            raise AttributeError("no config key %s%s" % (self._path, name)) from None
        if isinstance(value, dict):
            return Config(value, "%s%s." % (self._path, name))
        return value

    def __setattr__(self, name, value):
        raise AttributeError("configuration is read-only")

    def __getitem__(self, name):
        return self._data[name]

    def get(self, name, default=None):
        return self._data.get(name, default)

    def as_dict(self):
        return copy.deepcopy(self._data)


def load_config(path=None, environ=None, cli=None):
    """Build the effective configuration. `cli` maps dotted keys to flag values."""
    environ = os.environ if environ is None else environ
    data = copy.deepcopy(DEFAULTS)
    path = path or environ.get(env.CONFIG_FILE) or DEFAULT_PATH
    if os.path.exists(path):
        _merge(data, _rename_legacy(_read_yaml(path)), "")
    elif path != DEFAULT_PATH:
        raise ConfigError("config file not found: %s" % path)
    for key, value in env.overrides(environ).items():
        _set(data, key, value)
    for key, value in (cli or {}).items():
        if value is not None:
            _set(data, key, value)
    return Config(_coerce(data))


def _read_yaml(path):
    import yaml

    with open(path, encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise ConfigError("%s: the top level must be a mapping" % path)
    return loaded


def _rename_legacy(tree):
    tree = copy.deepcopy(tree)
    for old, new in RENAMED.items():
        section, old_key = old.split(".")
        new_key = new.split(".")[1]
        block = tree.get(section)
        if isinstance(block, dict) and old_key in block:
            block.setdefault(new_key, block.pop(old_key))
    policies = (tree.get("retry") or {}).get("policies") or {}
    for policy in policies.values():
        if not isinstance(policy, dict):
            continue
        for old, new in RENAMED.items():
            section, old_key = old.split(".")
            if section == "retry" and old_key in policy:
                policy.setdefault(new.split(".")[1], policy.pop(old_key))
    return tree


def _merge(base, over, prefix):
    for key, value in over.items():
        if prefix == "" and key not in base:
            raise ConfigError("unknown config section: %s" % key)
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value, prefix + key + ".")
        else:
            base[key] = copy.deepcopy(value)


def _set(data, dotted, value):
    section, key = dotted.split(".", 1)
    if section not in data:
        raise ConfigError("unknown config section: %s" % section)
    data[section][key] = value


def _coerce(data):
    for keys, fn in ((DURATION_KEYS, parse_duration), (SIZE_KEYS, parse_size), (INT_KEYS, int),
                     (FLOAT_KEYS, float), (LIST_KEYS, _as_list)):
        for dotted in keys:
            _apply(data, dotted, fn)
    for dotted, allowed in CHOICES.items():
        section, key = dotted.split(".")
        if data[section][key] not in allowed:
            raise ConfigError("%s must be one of: %s" % (dotted, ", ".join(allowed)))
    for name, policy in data["retry"]["policies"].items():
        unknown = sorted(set(policy) - set(POLICY_FIELDS))
        if unknown:
            raise ConfigError("retry.policies.%s: unknown keys %s" % (name, ", ".join(unknown)))
        for field in ("base_delay", "max_delay"):
            if field in policy:
                policy[field] = parse_duration(policy[field])
        if "multiplier" in policy:
            policy["multiplier"] = float(policy["multiplier"])
        if "max_attempts" in policy:
            policy["max_attempts"] = int(policy["max_attempts"])
    return data


def _apply(data, dotted, fn):
    section, key = dotted.split(".")
    try:
        data[section][key] = fn(data[section][key])
    except (TypeError, ValueError) as exc:
        raise ConfigError("%s: %s" % (dotted, exc)) from None


def _as_list(value):
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return list(value)
```

## tessera/errors.py

```python
"""Exception types. API-facing errors carry the HTTP status and error code they map to."""


class TesseraError(Exception):
    status = 500
    code = "internal_error"

    def to_dict(self):
        return {"error": self.code, "message": str(self) or self.code}


class ValidationError(TesseraError):
    status = 400
    code = "invalid_request"


class JobNotFound(TesseraError):
    status = 404
    code = "job_not_found"


class RunNotFound(TesseraError):
    status = 404
    code = "run_not_found"


class RouteNotFound(TesseraError):
    status = 404
    code = "not_found"


class MethodNotAllowed(TesseraError):
    status = 405
    code = "method_not_allowed"


class InvalidTransition(TesseraError):
    status = 409
    code = "invalid_transition"

    def __init__(self, current, wanted):
        super().__init__("cannot move job from %s to %s" % (current, wanted))
        self.current = current
        self.wanted = wanted


class IdempotencyConflict(TesseraError):
    status = 409
    code = "idempotency_conflict"


class Busy(TesseraError):
    status = 409
    code = "busy"


class RequestTooLarge(TesseraError):
    status = 413
    code = "request_too_large"


class PayloadTooLarge(TesseraError):
    status = 413
    code = "payload_too_large"


class PermanentError(Exception):
    """Raise from a job handler to fail the job without further retries."""


class UnknownJobType(PermanentError):
    pass
```

## tessera/models.py

```python
"""Domain objects shared by the API, the scheduler and the stores."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from tessera.errors import ValidationError
from tessera.util.timeutil import isoformat, parse_iso


class JobState:
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    DEAD = "dead"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset([JobState.SUCCEEDED, JobState.DEAD, JobState.CANCELLED])


class RunState:
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    LOST = "lost"


@dataclass
class JobSpec:
    job_type: str
    payload: Any
    queue: str
    priority: int = 0
    run_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data, default_queue):
        if not isinstance(data, dict):
            raise ValidationError("request body must be a JSON object")
        job_type = data.get("type")
        if not isinstance(job_type, str) or not job_type:
            raise ValidationError("'type' is required")
        if "payload" not in data:
            raise ValidationError("'payload' is required")
        priority = data.get("priority", 0)
        if not isinstance(priority, int) or not -100 <= priority <= 100:
            raise ValidationError("'priority' must be an integer between -100 and 100")
        try:
            run_at = parse_iso(data.get("run_at"))
        except ValueError:
            raise ValidationError("'run_at' must be an ISO 8601 timestamp") from None
        return cls(job_type, data["payload"], data.get("queue") or default_queue, priority, run_at)


@dataclass
class StoredPayload:
    inline: Optional[bytes] = None
    ref: Optional[str] = None
    size: int = 0


@dataclass
class Job:
    id: str
    job_type: str
    queue: str
    state: str
    priority: int
    run_at: Optional[datetime]
    attempts: int
    payload_size: int
    payload_inline: Optional[bytes]
    payload_ref: Optional[str]
    created_at: datetime
    updated_at: datetime

    def to_dict(self):
        return {
            "id": self.id, "type": self.job_type, "queue": self.queue, "state": self.state,
            "priority": self.priority, "run_at": isoformat(self.run_at), "attempts": self.attempts,
            "payload_size": self.payload_size, "created_at": isoformat(self.created_at),
            "updated_at": isoformat(self.updated_at),
        }


@dataclass
class Run:
    id: str
    job_id: str
    attempt: int
    owner: str
    state: str
    started_at: datetime
    lease_until: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    output: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id, "job_id": self.job_id, "attempt": self.attempt, "owner": self.owner,
            "state": self.state, "started_at": isoformat(self.started_at),
            "finished_at": isoformat(self.finished_at), "error": self.error,
        }
```

## tessera/payload.py

```python
"""Job payload encoding and the payload size policy."""
import json

from tessera.errors import PayloadTooLarge
from tessera.models import StoredPayload


def encode(payload):
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decode(blob):
    return json.loads(blob.decode("utf-8"))


def prepare_payload(payload, jobs_cfg, store):
    """Encode `payload` for storage according to jobs.max_payload_bytes and jobs.payload_overflow."""
    blob = encode(payload)
    limit = jobs_cfg.max_payload_bytes
    if len(blob) <= limit:
        return StoredPayload(inline=blob, size=len(blob))
    if jobs_cfg.payload_overflow == "spill":
        return StoredPayload(ref=store.spill_payload(blob), size=len(blob))
    raise PayloadTooLarge("payload is %d bytes; the limit is %d" % (len(blob), limit))


def load_payload(job, store):
    if job.payload_ref is not None:
        return decode(store.read_blob(job.payload_ref))
    return decode(job.payload_inline)
```

## tessera/runtime.py

```python
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
```

## tessera/scheduler/__init__.py

```python
"""Scheduling: claiming jobs, retry decisions, job locks and leader election."""
from tessera.scheduler.backoff import compute_delay
from tessera.scheduler.dispatch import Dispatcher
from tessera.scheduler.leader import LeaderElector, StaticElector, build_elector
from tessera.scheduler.locks import JobLock, LockManager, LockTimeout, lease_expiry
from tessera.scheduler.retry import RetryDecision, RetryPlanner, RetryPolicy

__all__ = [
    "Dispatcher", "JobLock", "LeaderElector", "LockManager", "LockTimeout", "RetryDecision",
    "RetryPlanner", "RetryPolicy", "StaticElector", "build_elector", "compute_delay", "lease_expiry",
]
```

## tessera/scheduler/backoff.py

```python
"""Retry delay calculation."""
import random


def compute_delay(base, multiplier, cap, attempt):
    """Seconds to wait after failed attempt number `attempt` (the first attempt is 1).

    The delay grows geometrically from `base` and never exceeds `cap`.
    """
    if attempt < 1:
        raise ValueError("attempt numbers start at 1, got %r" % (attempt,))
    return min(cap, base * multiplier ** (attempt - 1))


def with_jitter(delay, spread=0.1, rng=random):
    """Spread `delay` by up to +/- `spread` (a fraction) so that retries do not arrive in step."""
    if spread <= 0:
        return delay
    return delay * (1.0 + rng.uniform(-spread, spread))


def schedule(base, multiplier, cap, max_attempts):
    """Every delay a job can see, in order; used by the admin API."""
    return [compute_delay(base, multiplier, cap, n) for n in range(1, max_attempts)]
```

## tessera/scheduler/dispatch.py

```python
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
```

## tessera/scheduler/leader.py

```python
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
```

## tessera/scheduler/locks.py

```python
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
```

## tessera/scheduler/retry.py

```python
"""Deciding whether, and when, a failed run is tried again."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from tessera.errors import PermanentError
from tessera.scheduler.backoff import compute_delay
from tessera.util.timeutil import utcnow

_FIELDS = ("max_attempts", "base_delay", "multiplier", "max_delay")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay: float
    multiplier: float
    max_delay: float

    @classmethod
    def resolve(cls, retry_cfg, job_type):
        """The global retry settings, overlaid with the job type's entry under retry.policies."""
        values = {name: retry_cfg[name] for name in _FIELDS}
        values.update(retry_cfg.policies.get(job_type) or {})
        return cls(**values)


@dataclass(frozen=True)
class RetryDecision:
    attempt: int
    retry: bool
    delay: float
    run_at: Optional[datetime]
    error: str


class RetryPlanner:
    def __init__(self, retry_cfg, clock=utcnow):
        self._cfg = retry_cfg
        self._clock = clock
        self._policies = {}

    def policy_for(self, job_type):
        policy = self._policies.get(job_type)
        if policy is None:
            policy = self._policies[job_type] = RetryPolicy.resolve(self._cfg, job_type)
        return policy

    def decide(self, job, attempt, exc):
        """Decision for `job` after its run number `attempt` raised `exc`."""
        error = describe(exc)
        policy = self.policy_for(job.job_type)
        if isinstance(exc, PermanentError) or attempt >= policy.max_attempts:
            return RetryDecision(attempt, False, 0.0, None, error)
        delay = compute_delay(policy.base_delay, policy.multiplier, policy.max_delay, attempt)
        return RetryDecision(attempt, True, delay, self._clock() + timedelta(seconds=delay), error)


def describe(exc):
    text = "%s: %s" % (type(exc).__name__, exc)
    return text if len(text) <= 2000 else text[:1997] + "..."
```

## tessera/storage/__init__.py

```python
"""Storage backends. open_store() picks one from the scheme of storage.url."""
from tessera.storage.attempts import record_attempt
from tessera.storage.base import Store

__all__ = ["Store", "migrate", "open_store", "record_attempt"]


def open_store(storage_cfg):
    url = storage_cfg.url
    scheme = url.split(":", 1)[0].lower()
    if scheme in ("postgres", "postgresql"):
        from tessera.storage.postgres import PostgresStore

        return PostgresStore(url, pool_size=storage_cfg.pool_size, statement_timeout=storage_cfg.statement_timeout)
    if scheme == "sqlite":
        from tessera.storage.sqlite import SqliteStore

        return SqliteStore(url[len("sqlite://"):])
    raise ValueError("unsupported storage url: %s" % url)


def migrate(storage_cfg, dry_run=False):
    store = open_store(storage_cfg)
    try:
        return store.migrate(dry_run=dry_run)
    finally:
        store.close()
```

## tessera/storage/attempts.py

```python
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
```

## tessera/storage/base.py

```python
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
```

## tessera/storage/postgres.py

```python
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
```

## tessera/storage/sql.py

```python
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
```

## tessera/storage/sqlite.py

```python
"""SQLite backend for development and single-machine deployments."""
import contextlib
import os
import sqlite3
import threading
from datetime import datetime

from tessera.storage.sql import SqlStore
from tessera.util.timeutil import isoformat

sqlite3.register_adapter(datetime, isoformat)
sqlite3.register_converter("TIMESTAMPTZ", lambda raw: datetime.fromisoformat(raw.decode().replace("Z", "+00:00")))


class SqliteStore(SqlStore):
    def __init__(self, path):
        super().__init__()
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        if os.environ.get("TESSERA_SINGLE_NODE"):
            self._conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        self._mutex = threading.RLock()

    @contextlib.contextmanager
    def _connection(self):
        with self._mutex:
            yield self._conn

    def close(self):
        with self._mutex:
            self._conn.close()
```

## tessera/util/__init__.py

```python
"""Small helpers with no dependencies on the rest of tessera: ids, durations, sizes."""
import os
import re
import time

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)")
_DURATION_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmg]i?b|b)?\s*$", re.I)
_SIZE_UNITS = {"b": 1, "kb": 1000, "mb": 1000 ** 2, "gb": 1000 ** 3,
               "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3}


def new_id(prefix):
    """Sortable id: a millisecond timestamp followed by 60 random bits, base32."""
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(8), "big") >> 4
    return "%s_%s%s" % (prefix, _b32(ms, 9), _b32(rand, 12))


def _b32(n, width):
    out = []
    for _ in range(width):
        n, r = divmod(n, 32)
        out.append(_ALPHABET[r])
    return "".join(reversed(out))


def parse_duration(value):
    """Seconds as a float. Bare numbers are seconds; strings may chain units ("1h30m")."""
    if isinstance(value, bool):
        raise ValueError("not a duration: %r" % (value,))
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().replace(" ", "")
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    pos, total = 0, 0.0
    for m in _DURATION_PART.finditer(text):
        if m.start() != pos:
            break
        total += float(m.group(1)) * _DURATION_UNITS[m.group(2)]
        pos = m.end()
    if pos == 0 or pos != len(text):
        raise ValueError("not a duration: %r" % (value,))
    return total


def parse_size(value):
    """Bytes as an int. Accepts decimal (kB, MB, GB) and binary (KiB, MiB, GiB) units."""
    if isinstance(value, bool):
        raise ValueError("not a size: %r" % (value,))
    if isinstance(value, int):
        return value
    m = _SIZE.match(str(value))
    if not m:
        raise ValueError("not a size: %r" % (value,))
    return int(float(m.group(1)) * _SIZE_UNITS[(m.group(2) or "b").lower()])
```

## tessera/util/timeutil.py

```python
"""Time helpers.

All timestamps inside tessera are timezone-aware UTC datetimes and all
durations are float seconds.
"""
from datetime import datetime, timedelta, timezone

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def utcnow():
    return datetime.now(timezone.utc)


def ensure_utc(ts):
    """Attach UTC to naive datetimes (SQLite returns those); convert aware ones."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def lease_expiry(now, ttl_seconds):
    """The instant at which a lease taken at `now` for `ttl_seconds` lapses."""
    if ttl_seconds <= 0:
        raise ValueError("lease ttl must be positive, got %r" % (ttl_seconds,))
    return ensure_utc(now) + timedelta(seconds=ttl_seconds)


def seconds_until(ts, now=None):
    now = now or utcnow()
    return max(0.0, (ensure_utc(ts) - now).total_seconds())


def to_epoch(ts):
    return (ensure_utc(ts) - EPOCH).total_seconds()


def isoformat(ts):
    if ts is None:
        return None
    return ensure_utc(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_iso(text):
    if text is None:
        return None
    return ensure_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
```

## tessera/worker.py

```python
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
```

## migrations/001_init.sql

```sql
-- Initial schema: jobs, runs, attempt history, dead letters, oversized payloads.

CREATE TABLE jobs (
    id            TEXT PRIMARY KEY,
    job_type      TEXT NOT NULL,
    queue         TEXT NOT NULL,
    state         TEXT NOT NULL,
    priority      INTEGER NOT NULL DEFAULT 0,
    run_at        TIMESTAMPTZ,
    attempts      INTEGER NOT NULL DEFAULT 0,
    payload_size  INTEGER NOT NULL,
    payload       BYTEA,
    payload_ref   TEXT,
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX jobs_runnable ON jobs (state, queue, priority, run_at);

CREATE TABLE runs (
    id           TEXT PRIMARY KEY,
    job_id       TEXT NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    attempt      INTEGER NOT NULL,
    owner        TEXT NOT NULL,
    state        TEXT NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL,
    lease_until  TIMESTAMPTZ NOT NULL,
    finished_at  TIMESTAMPTZ,
    error        TEXT,
    output       TEXT
);

CREATE INDEX runs_by_job ON runs (job_id, attempt);

CREATE TABLE job_attempts (
    job_id       TEXT NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    attempt      INTEGER NOT NULL,
    error        TEXT,
    delay_s      DOUBLE PRECISION,
    next_run_at  TIMESTAMPTZ,
    recorded_at  TIMESTAMPTZ NOT NULL,
    UNIQUE (job_id, attempt)
);

CREATE TABLE dead_letters (
    job_id      TEXT PRIMARY KEY REFERENCES jobs (id) ON DELETE CASCADE,
    reason      TEXT,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE payload_overflow (
    id          TEXT PRIMARY KEY,
    body        BYTEA NOT NULL,
    size        INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);
```

## migrations/002_coordination.sql

```sql
-- Locks, leader lease and idempotency keys; payload_overflow gets its final name.

ALTER TABLE payload_overflow RENAME TO job_blobs;

CREATE TABLE job_locks (
    lock_key    TEXT PRIMARY KEY,
    owner       TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE leader_lease (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    holder      TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE idempotency_keys (
    idem_key     TEXT NOT NULL,
    scope        TEXT NOT NULL,
    fingerprint  TEXT NOT NULL,
    status       INTEGER NOT NULL,
    body         BYTEA,
    expires_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (idem_key, scope)
);

CREATE INDEX idempotency_keys_expiry ON idempotency_keys (expires_at);
```

## clients/ts/package.json

```json
{
  "name": "@tessera/client",
  "version": "0.14.0",
  "description": "TypeScript client for the tessera job scheduler API",
  "type": "module",
  "main": "dist/client.js",
  "types": "dist/client.d.ts",
  "files": ["dist"],
  "scripts": {
    "build": "tsc -p .",
    "test": "node --test test/"
  },
  "engines": { "node": ">=18" },
  "devDependencies": { "typescript": "^5.4.0" }
}
```

## clients/ts/src/client.ts

```ts
import { HttpTransport, type TransportOptions } from "./http";
import { paths } from "./paths";

export { HttpError } from "./http";
export { HEADERS, IDEMPOTENCY_HEADER } from "./constants";

export type JobState = "queued" | "scheduled" | "running" | "paused" | "succeeded" | "dead" | "cancelled";

export interface JobSpec {
  type: string;
  payload: unknown;
  queue?: string;
  priority?: number;
  run_at?: string;
}

export interface Job {
  id: string;
  type: string;
  queue: string;
  state: JobState;
  priority: number;
  run_at: string | null;
  attempts: number;
  payload_size: number;
  created_at: string;
  updated_at: string;
}

export interface Run {
  id: string;
  job_id: string;
  attempt: number;
  owner: string;
  state: "running" | "succeeded" | "failed" | "lost";
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface Page<T> {
  items: T[];
  next: string | null;
}

export interface ListJobsFilter {
  state?: JobState;
  queue?: string;
  limit?: number;
  after?: string;
}

const FINAL: ReadonlySet<JobState> = new Set<JobState>(["succeeded", "dead", "cancelled"]);

export class TesseraClient {
  private readonly http: HttpTransport;

  constructor(baseUrl: string, options: TransportOptions = {}) {
    this.http = new HttpTransport(baseUrl, options);
  }

  createJob(spec: JobSpec, opts: { idempotencyKey?: string } = {}): Promise<Job> {
    return this.http.request("POST", paths.jobs(), { body: spec, idempotent: true, ...opts });
  }

  getJob(id: string): Promise<Job> {
    return this.http.request("GET", paths.job(id));
  }

  listJobs(filter: ListJobsFilter = {}): Promise<Page<Job>> {
    return this.http.request("GET", paths.jobs(), { query: { ...filter } });
  }

  cancelJob(id: string): Promise<Job> {
    return this.http.request("POST", paths.jobAction(id, "cancel"));
  }

  pauseJob(id: string): Promise<Job> {
    return this.http.request("POST", paths.jobAction(id, "pause"));
  }

  resumeJob(id: string): Promise<Job> {
    return this.http.request("POST", paths.jobAction(id, "resume"));
  }

  listRuns(jobId: string): Promise<Page<Run>> {
    return this.http.request("GET", paths.jobRuns(jobId));
  }

  runNow(jobId: string, opts: { idempotencyKey?: string } = {}): Promise<Job> {
    return this.http.request("POST", paths.jobRuns(jobId), { idempotent: true, ...opts });
  }

  triggerJob(jobId: string): Promise<Job> {
    return this.http.request("POST", `${paths.job(jobId)}/trigger`);
  }

  getRun(runId: string): Promise<Run> {
    return this.http.request("GET", paths.run(runId));
  }

  getRunOutput<T = unknown>(runId: string): Promise<T | undefined> {
    return this.http.request("GET", paths.runOutput(runId));
  }

  requeueDeadJob(jobId: string): Promise<Job> {
    return this.http.request("POST", paths.admin.requeue(jobId), { idempotent: true });
  }

  async waitForJob(id: string, { intervalMs = 1000, timeoutMs = 300_000 } = {}): Promise<Job> {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const job = await this.getJob(id);
      if (FINAL.has(job.state)) return job;
      if (Date.now() + intervalMs > deadline) throw new Error(`job ${id} still ${job.state} after ${timeoutMs}ms`);
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }
}
```

## clients/ts/src/constants.ts

```ts
export const API_VERSION = "v1";

export const IDEMPOTENCY_HEADER = "Idempotency-Key";

export const HEADERS = {
  idempotency: "X-Tessera-Idem-Key",
  client: "X-Tessera-Client",
  requestId: "X-Request-Id",
} as const;

export const CLIENT_NAME = "tessera-ts/0.14";
export const DEFAULT_TIMEOUT_MS = 30_000;
export const RETRYABLE_STATUS: readonly number[] = [502, 503, 504];
```

## clients/ts/src/http.ts

```ts
import { CLIENT_NAME, DEFAULT_TIMEOUT_MS, HEADERS, RETRYABLE_STATUS } from "./constants";

export interface TransportOptions {
  token?: string;
  timeoutMs?: number;
  retries?: number;
  fetch?: typeof fetch;
}

export interface RequestOptions {
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  idempotent?: boolean;
  idempotencyKey?: string;
  signal?: AbortSignal;
}

export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export class HttpTransport {
  private readonly fetchImpl: typeof fetch;

  constructor(
    private readonly baseUrl: string,
    private readonly options: TransportOptions = {},
  ) {
    this.fetchImpl = options.fetch ?? globalThis.fetch;
  }

  async request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
    const url = new URL(path, this.baseUrl);
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
    const headers: Record<string, string> = { Accept: "application/json", [HEADERS.client]: CLIENT_NAME };
    if (this.options.token) headers.Authorization = `Bearer ${this.options.token}`;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (opts.idempotent) headers[HEADERS.idempotency] = opts.idempotencyKey ?? newKey();

    const canRetry = method === "GET" || opts.idempotent === true;
    const attempts = canRetry ? 1 + (this.options.retries ?? 2) : 1;
    let last: unknown;
    for (let i = 0; i < attempts; i++) {
      if (i > 0) await sleep(250 * 2 ** (i - 1));
      const res = await this.fetchImpl(url, {
        method,
        headers,
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
        signal: opts.signal ?? AbortSignal.timeout(this.options.timeoutMs ?? DEFAULT_TIMEOUT_MS),
      });
      if (res.ok) {
        return (res.status === 204 ? undefined : await res.json()) as T;
      }
      const err = await toError(res);
      if (!RETRYABLE_STATUS.includes(res.status)) throw err;
      last = err;
    }
    throw last;
  }
}

async function toError(res: Response): Promise<HttpError> {
  try {
    const body = (await res.json()) as { error?: string; message?: string };
    return new HttpError(res.status, body.error ?? "unknown", body.message ?? res.statusText);
  } catch {
    return new HttpError(res.status, "unknown", res.statusText);
  }
}

function newKey(): string {
  return globalThis.crypto.randomUUID();
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
```

## clients/ts/src/paths.ts

```ts
import { API_VERSION } from "./constants";

const base = `/${API_VERSION}`;
const enc = encodeURIComponent;

export type JobAction = "cancel" | "pause" | "resume";

export const paths = {
  jobs: () => `${base}/jobs`,
  job: (id: string) => `${base}/jobs/${enc(id)}`,
  jobAction: (id: string, action: JobAction) => `${base}/jobs/${enc(id)}/${action}`,
  jobRuns: (id: string) => `${base}/jobs/${enc(id)}/runs`,
  run: (id: string) => `${base}/runs/${enc(id)}`,
  runOutput: (id: string) => `${base}/runs/${enc(id)}/output`,
  admin: {
    leader: () => `${base}/admin/leader`,
    deadLetters: () => `${base}/admin/dead-letters`,
    requeue: (id: string) => `${base}/admin/jobs/${enc(id)}/requeue`,
    drain: () => `${base}/admin/drain`,
  },
};
```

## tests/test_config.py

```python
import pytest

from tessera.config import ConfigError, load_config, loader
from tessera.scheduler.backoff import compute_delay
from tessera.scheduler.retry import RetryPolicy


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    def make(tree):
        path = tmp_path / "tessera.yaml"
        path.write_text("# replaced by the fixture\n")
        monkeypatch.setattr(loader, "_read_yaml", lambda _: tree)
        return str(path)

    return make


def test_env_overrides_yaml(config_file):
    cfg = load_config(config_file({"retry": {"max_delay": "2m"}}), environ={"TESSERA_RETRY_MAX_DELAY": "45"})
    assert cfg.retry.max_delay == 45.0


def test_flag_overrides_env(config_file):
    cfg = load_config(config_file({}), environ={"TESSERA_API_PORT": "9000"}, cli={"api.port": 9100})
    assert cfg.api.port == 9100


def test_legacy_key_is_renamed(config_file):
    assert load_config(config_file({"retry": {"cap": "90s"}}), environ={}).retry.max_delay == 90.0


def test_unknown_section_is_rejected(config_file):
    with pytest.raises(ConfigError):
        load_config(config_file({"workers": {"concurrency": 2}}), environ={})


def test_policy_inherits_unset_fields(config_file):
    cfg = load_config(config_file({"retry": {"max_attempts": 4, "policies": {"thumb": {"base_delay": "3s"}}}}),
                      environ={})
    assert RetryPolicy.resolve(cfg.retry, "thumb") == RetryPolicy(4, 3.0, 2.0, 300.0)


def test_compute_delay_is_capped():
    assert [compute_delay(1, 2, 10, n) for n in range(1, 7)] == [1, 2, 4, 8, 10, 10]


def test_attempt_numbers_start_at_one():
    with pytest.raises(ValueError):
        compute_delay(1, 2, 10, 0)
```
