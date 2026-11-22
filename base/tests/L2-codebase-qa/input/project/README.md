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
