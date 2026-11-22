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
