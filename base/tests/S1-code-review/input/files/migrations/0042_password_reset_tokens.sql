-- 0042: password reset tokens
-- All timestamps are stored in UTC without a time zone, like the rest of the schema.

-- +migrate up
CREATE TABLE password_reset_tokens (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_digest  CHAR(64) NOT NULL UNIQUE,
    expires_at    TIMESTAMP NOT NULL,
    used_at       TIMESTAMP,
    created_at    TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE INDEX password_reset_tokens_user_id_idx ON password_reset_tokens (user_id);

ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP;

-- +migrate down
DROP INDEX password_reset_tokens_user_id_idx;
DROP TABLE password_reset_tokens;
ALTER TABLE users DROP COLUMN password_hash;
