"""Retry delay calculation."""
import random


def compute_delay(base, multiplier, cap, attempt):
    """Seconds to wait after failed attempt number `attempt` (the first attempt is 1).

    The delay grows geometrically from `base` and never exceeds `cap`.
    """
    if attempt < 1:
        raise ValueError("attempt numbers start at 1, got %r" % (attempt,))
    return min(cap, base * multiplier ** (attempt - 1))


def with_jitter(delay, spread=0.1, rng=random):
    """Spread `delay` by up to +/- `spread` (a fraction) so that retries do not arrive in step."""
    if spread <= 0:
        return delay
    return delay * (1.0 + rng.uniform(-spread, spread))


def schedule(base, multiplier, cap, max_attempts):
    """Every delay a job can see, in order; used by the admin API."""
    return [compute_delay(base, multiplier, cap, n) for n in range(1, max_attempts)]
