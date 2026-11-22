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
