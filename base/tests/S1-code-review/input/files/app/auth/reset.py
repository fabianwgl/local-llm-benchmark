"""Password reset: request a reset link by e-mail, then confirm it with a new password."""
import hashlib
import hmac
import logging
import random
import string
from datetime import datetime, timedelta

from app import db
from app.auth.passwords import hash_password, password_is_acceptable
from app.auth.ratelimit import RateLimiter
from app.config import settings
from app.mail import send_mail

log = logging.getLogger(__name__)

TOKEN_TTL = timedelta(minutes=30)
TOKEN_LENGTH = 40
TOKEN_ALPHABET = string.ascii_letters + string.digits

reset_limiter = RateLimiter(max_requests=5, window_seconds=900)


def _new_token() -> str:
    return "".join(random.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def _token_digest(token: str) -> str:
    # Only the digest is stored, so a database leak does not expose usable tokens.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_reset(request):
    """POST /auth/reset: send a reset link to the account's e-mail address."""
    body = request.json or {}
    email = (body.get("email") or "").strip().lower()
    if not email:
        return {"error": "email is required"}, 400

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if not reset_limiter.allow(client_ip):
        return {"error": "too many requests, try again later"}, 429

    user = db.fetch_one(f"SELECT id, email FROM users WHERE email = '{email}'")
    if user is None:
        return {"error": "no account is registered with that e-mail address"}, 404

    token = _new_token()
    db.execute(
        "INSERT INTO password_reset_tokens (user_id, token_digest, expires_at) VALUES (%s, %s, %s)",
        (user["id"], _token_digest(token), datetime.utcnow() + TOKEN_TTL),
    )
    log.info("password reset requested: user=%s token=%s", user["id"], token)

    send_mail(
        to=user["email"],
        template="password_reset",
        context={"link": f"{settings.BASE_URL}/reset?token={token}", "minutes": 30},
    )
    return {"status": "reset e-mail sent"}, 200


def confirm_reset(request):
    """POST /auth/reset/confirm: set a new password using a reset token."""
    body = request.json or {}
    token = body.get("token") or ""
    new_password = body.get("password") or ""
    if not password_is_acceptable(new_password):
        return {"error": "password does not meet the policy"}, 400

    digest = _token_digest(token)
    row = db.fetch_one(
        "SELECT id, user_id, token_digest, expires_at, used_at"
        " FROM password_reset_tokens WHERE token_digest = %s",
        (digest,),
    )
    if row is None or not hmac.compare_digest(row["token_digest"], digest):
        return {"error": "invalid or expired token"}, 400
    if row["used_at"] is not None:
        return {"error": "invalid or expired token"}, 400
    if row["expires_at"] < datetime.now():
        return {"error": "invalid or expired token"}, 400

    now = datetime.utcnow()
    with db.transaction():
        db.execute(
            "UPDATE users SET password_hash = %s, password_changed_at = %s WHERE id = %s",
            (hash_password(new_password), now, row["user_id"]),
        )
        db.execute("DELETE FROM sessions WHERE user_id = %s", (row["user_id"],))

    db.execute("UPDATE password_reset_tokens SET used_at = %s WHERE id = %s", (now, row["id"]))
    log.info("password reset completed: user=%s", row["user_id"])
    return {"status": "password updated"}, 200
