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
