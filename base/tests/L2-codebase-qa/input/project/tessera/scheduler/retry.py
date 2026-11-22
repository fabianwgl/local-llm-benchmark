"""Deciding whether, and when, a failed run is tried again."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from tessera.errors import PermanentError
from tessera.scheduler.backoff import compute_delay
from tessera.util.timeutil import utcnow

_FIELDS = ("max_attempts", "base_delay", "multiplier", "max_delay")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay: float
    multiplier: float
    max_delay: float

    @classmethod
    def resolve(cls, retry_cfg, job_type):
        """The global retry settings, overlaid with the job type's entry under retry.policies."""
        values = {name: retry_cfg[name] for name in _FIELDS}
        values.update(retry_cfg.policies.get(job_type) or {})
        return cls(**values)


@dataclass(frozen=True)
class RetryDecision:
    attempt: int
    retry: bool
    delay: float
    run_at: Optional[datetime]
    error: str


class RetryPlanner:
    def __init__(self, retry_cfg, clock=utcnow):
        self._cfg = retry_cfg
        self._clock = clock
        self._policies = {}

    def policy_for(self, job_type):
        policy = self._policies.get(job_type)
        if policy is None:
            policy = self._policies[job_type] = RetryPolicy.resolve(self._cfg, job_type)
        return policy

    def decide(self, job, attempt, exc):
        """Decision for `job` after its run number `attempt` raised `exc`."""
        error = describe(exc)
        policy = self.policy_for(job.job_type)
        if isinstance(exc, PermanentError) or attempt >= policy.max_attempts:
            return RetryDecision(attempt, False, 0.0, None, error)
        delay = compute_delay(policy.base_delay, policy.multiplier, policy.max_delay, attempt)
        return RetryDecision(attempt, True, delay, self._clock() + timedelta(seconds=delay), error)


def describe(exc):
    text = "%s: %s" % (type(exc).__name__, exc)
    return text if len(text) <= 2000 else text[:1997] + "..."
