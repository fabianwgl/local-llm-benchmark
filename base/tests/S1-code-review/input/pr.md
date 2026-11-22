### `app/auth/reset.py` (new file)

```
   1 + """Password reset: request a reset link by e-mail, then confirm it with a new password."""
   2 + import hashlib
   3 + import hmac
   4 + import logging
   5 + import random
   6 + import string
   7 + from datetime import datetime, timedelta
   8 + 
   9 + from app import db
  10 + from app.auth.passwords import hash_password, password_is_acceptable
  11 + from app.auth.ratelimit import RateLimiter
  12 + from app.config import settings
  13 + from app.mail import send_mail
  14 + 
  15 + log = logging.getLogger(__name__)
  16 + 
  17 + TOKEN_TTL = timedelta(minutes=30)
  18 + TOKEN_LENGTH = 40
  19 + TOKEN_ALPHABET = string.ascii_letters + string.digits
  20 + 
  21 + reset_limiter = RateLimiter(max_requests=5, window_seconds=900)
  22 + 
  23 + 
  24 + def _new_token() -> str:
  25 +     return "".join(random.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))
  26 + 
  27 + 
  28 + def _token_digest(token: str) -> str:
  29 +     # Only the digest is stored, so a database leak does not expose usable tokens.
  30 +     return hashlib.sha256(token.encode("utf-8")).hexdigest()
  31 + 
  32 + 
  33 + def request_reset(request):
  34 +     """POST /auth/reset: send a reset link to the account's e-mail address."""
  35 +     body = request.json or {}
  36 +     email = (body.get("email") or "").strip().lower()
  37 +     if not email:
  38 +         return {"error": "email is required"}, 400
  39 + 
  40 +     client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
  41 +     if not reset_limiter.allow(client_ip):
  42 +         return {"error": "too many requests, try again later"}, 429
  43 + 
  44 +     user = db.fetch_one(f"SELECT id, email FROM users WHERE email = '{email}'")
  45 +     if user is None:
  46 +         return {"error": "no account is registered with that e-mail address"}, 404
  47 + 
  48 +     token = _new_token()
  49 +     db.execute(
  50 +         "INSERT INTO password_reset_tokens (user_id, token_digest, expires_at) VALUES (%s, %s, %s)",
  51 +         (user["id"], _token_digest(token), datetime.utcnow() + TOKEN_TTL),
  52 +     )
  53 +     log.info("password reset requested: user=%s token=%s", user["id"], token)
  54 + 
  55 +     send_mail(
  56 +         to=user["email"],
  57 +         template="password_reset",
  58 +         context={"link": f"{settings.BASE_URL}/reset?token={token}", "minutes": 30},
  59 +     )
  60 +     return {"status": "reset e-mail sent"}, 200
  61 + 
  62 + 
  63 + def confirm_reset(request):
  64 +     """POST /auth/reset/confirm: set a new password using a reset token."""
  65 +     body = request.json or {}
  66 +     token = body.get("token") or ""
  67 +     new_password = body.get("password") or ""
  68 +     if not password_is_acceptable(new_password):
  69 +         return {"error": "password does not meet the policy"}, 400
  70 + 
  71 +     digest = _token_digest(token)
  72 +     row = db.fetch_one(
  73 +         "SELECT id, user_id, token_digest, expires_at, used_at"
  74 +         " FROM password_reset_tokens WHERE token_digest = %s",
  75 +         (digest,),
  76 +     )
  77 +     if row is None or not hmac.compare_digest(row["token_digest"], digest):
  78 +         return {"error": "invalid or expired token"}, 400
  79 +     if row["used_at"] is not None:
  80 +         return {"error": "invalid or expired token"}, 400
  81 +     if row["expires_at"] < datetime.now():
  82 +         return {"error": "invalid or expired token"}, 400
  83 + 
  84 +     now = datetime.utcnow()
  85 +     with db.transaction():
  86 +         db.execute(
  87 +             "UPDATE users SET password_hash = %s, password_changed_at = %s WHERE id = %s",
  88 +             (hash_password(new_password), now, row["user_id"]),
  89 +         )
  90 +         db.execute("DELETE FROM sessions WHERE user_id = %s", (row["user_id"],))
  91 + 
  92 +     db.execute("UPDATE password_reset_tokens SET used_at = %s WHERE id = %s", (now, row["id"]))
  93 +     log.info("password reset completed: user=%s", row["user_id"])
  94 +     return {"status": "password updated"}, 200
```

### `app/auth/ratelimit.py` (new file)

```
   1 + """A small in-process sliding-window rate limiter."""
   2 + import threading
   3 + import time
   4 + from collections import defaultdict, deque
   5 + 
   6 + 
   7 + class RateLimiter:
   8 +     """Allow at most `max_requests` per `window_seconds` for each key."""
   9 + 
  10 +     def __init__(self, max_requests: int, window_seconds: int):
  11 +         if max_requests < 1 or window_seconds < 1:
  12 +             raise ValueError("max_requests and window_seconds must be positive")
  13 +         self.max_requests = max_requests
  14 +         self.window_seconds = window_seconds
  15 +         self._hits = defaultdict(deque)
  16 +         self._lock = threading.Lock()
  17 + 
  18 +     def allow(self, key: str) -> bool:
  19 +         now = time.monotonic()
  20 +         cutoff = now - self.window_seconds
  21 +         with self._lock:
  22 +             hits = self._hits[key]
  23 +             while hits and hits[0] < cutoff:
  24 +                 hits.popleft()
  25 +             if len(hits) >= self.max_requests:
  26 +                 return False
  27 +             hits.append(now)
  28 +             return True
```

### `migrations/0042_password_reset_tokens.sql` (new file)

```
   1 + -- 0042: password reset tokens
   2 + -- All timestamps are stored in UTC without a time zone, like the rest of the schema.
   3 + 
   4 + -- +migrate up
   5 + CREATE TABLE password_reset_tokens (
   6 +     id            BIGSERIAL PRIMARY KEY,
   7 +     user_id       BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
   8 +     token_digest  CHAR(64) NOT NULL UNIQUE,
   9 +     expires_at    TIMESTAMP NOT NULL,
  10 +     used_at       TIMESTAMP,
  11 +     created_at    TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
  12 + );
  13 + 
  14 + CREATE INDEX password_reset_tokens_user_id_idx ON password_reset_tokens (user_id);
  15 + 
  16 + ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP;
  17 + 
  18 + -- +migrate down
  19 + DROP INDEX password_reset_tokens_user_id_idx;
  20 + DROP TABLE password_reset_tokens;
  21 + ALTER TABLE users DROP COLUMN password_hash;
```

### `deploy/hooks/post_deploy.sh` (modified)

```
   1   #!/usr/bin/env bash
   2   # Runs on the release host after the new build is unpacked and before traffic is switched.
   3   set -euo pipefail
   4   
   5   RELEASE_TMP="${RELEASE_TMP:-/var/tmp/app-release}"
   6 + MIGRATE_TO="${MIGRATE_TO:-0042}"
   7   
   8 + echo "post-deploy: applying migrations up to ${MIGRATE_TO}"
   9 + python -m app.migrate up --to "${MIGRATE_TO}"
  10   
  11   echo "post-deploy: clearing release scratch space"
  12   rm -rf "${RELEASE_TMP:?}"/*
  13   
  14   echo "post-deploy: warming caches"
  15   python -m app.cache warm
```

## Existing files, unchanged by this PR (for context)

### `app/db.py`

```
   1   """Thin database helpers used across the app (PostgreSQL)."""
   2   from contextlib import contextmanager
   3   
   4   from app.pool import pool
   5   
   6   
   7   def fetch_one(sql: str, params: tuple = ()):
   8       """Return the first row as a dict, or None. Values must be passed in `params`, never formatted
   9       into `sql`."""
  10       with pool.cursor() as cur:
  11           cur.execute(sql, params)
  12           return cur.fetchone()
  13   
  14   
  15   def execute(sql: str, params: tuple = ()) -> int:
  16       """Run a statement and return the number of affected rows. Joins the current transaction if
  17       one is open; otherwise the statement is committed on its own."""
  18       with pool.cursor() as cur:
  19           cur.execute(sql, params)
  20           return cur.rowcount
  21   
  22   
  23   @contextmanager
  24   def transaction():
  25       """Run the enclosed statements atomically: commit on success, roll back on any exception."""
  26       with pool.transaction():
  27           yield
```

### `app/config.py`

```
   1   """Application settings. Conventions:
   2   
   3   - Every timestamp in the database is naive UTC; compare it only with `datetime.utcnow()`.
   4   - The app runs behind the company load balancer. `request.remote_addr` is already the real
   5     client address: the balancer strips client-supplied forwarding headers at the WSGI layer and
   6     sets REMOTE_ADDR itself. Headers such as `X-Forwarded-For` reach the app exactly as the
   7     client sent them.
   8   - Four worker processes serve requests on each host.
   9   """
  10   import os
  11   
  12   
  13   class Settings:
  14       BASE_URL = os.environ.get("BASE_URL", "https://app.example.com")
  15       DATABASE_URL = os.environ["DATABASE_URL"]
  16       LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
  17   
  18   
  19   settings = Settings()
```
