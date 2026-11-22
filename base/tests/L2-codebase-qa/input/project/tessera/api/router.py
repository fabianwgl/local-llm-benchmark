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
