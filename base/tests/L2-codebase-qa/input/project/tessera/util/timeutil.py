"""Time helpers.

All timestamps inside tessera are timezone-aware UTC datetimes and all
durations are float seconds.
"""
from datetime import datetime, timedelta, timezone

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def utcnow():
    return datetime.now(timezone.utc)


def ensure_utc(ts):
    """Attach UTC to naive datetimes (SQLite returns those); convert aware ones."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def lease_expiry(now, ttl_seconds):
    """The instant at which a lease taken at `now` for `ttl_seconds` lapses."""
    if ttl_seconds <= 0:
        raise ValueError("lease ttl must be positive, got %r" % (ttl_seconds,))
    return ensure_utc(now) + timedelta(seconds=ttl_seconds)


def seconds_until(ts, now=None):
    now = now or utcnow()
    return max(0.0, (ensure_utc(ts) - now).total_seconds())


def to_epoch(ts):
    return (ensure_utc(ts) - EPOCH).total_seconds()


def isoformat(ts):
    if ts is None:
        return None
    return ensure_utc(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_iso(text):
    if text is None:
        return None
    return ensure_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
