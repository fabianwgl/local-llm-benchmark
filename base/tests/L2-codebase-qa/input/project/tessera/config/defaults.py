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
