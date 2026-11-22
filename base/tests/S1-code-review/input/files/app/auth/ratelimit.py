"""A small in-process sliding-window rate limiter."""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Allow at most `max_requests` per `window_seconds` for each key."""

    def __init__(self, max_requests: int, window_seconds: int):
        if max_requests < 1 or window_seconds < 1:
            raise ValueError("max_requests and window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True
