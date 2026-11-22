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
