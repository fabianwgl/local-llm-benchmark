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
