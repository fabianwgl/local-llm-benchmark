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
