"""Domain objects shared by the API, the scheduler and the stores."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from tessera.errors import ValidationError
from tessera.util.timeutil import isoformat, parse_iso


class JobState:
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    DEAD = "dead"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset([JobState.SUCCEEDED, JobState.DEAD, JobState.CANCELLED])


class RunState:
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    LOST = "lost"


@dataclass
class JobSpec:
    job_type: str
    payload: Any
    queue: str
    priority: int = 0
    run_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data, default_queue):
        if not isinstance(data, dict):
            raise ValidationError("request body must be a JSON object")
        job_type = data.get("type")
        if not isinstance(job_type, str) or not job_type:
            raise ValidationError("'type' is required")
        if "payload" not in data:
            raise ValidationError("'payload' is required")
        priority = data.get("priority", 0)
        if not isinstance(priority, int) or not -100 <= priority <= 100:
            raise ValidationError("'priority' must be an integer between -100 and 100")
        try:
            run_at = parse_iso(data.get("run_at"))
        except ValueError:
            raise ValidationError("'run_at' must be an ISO 8601 timestamp") from None
        return cls(job_type, data["payload"], data.get("queue") or default_queue, priority, run_at)


@dataclass
class StoredPayload:
    inline: Optional[bytes] = None
    ref: Optional[str] = None
    size: int = 0


@dataclass
class Job:
    id: str
    job_type: str
    queue: str
    state: str
    priority: int
    run_at: Optional[datetime]
    attempts: int
    payload_size: int
    payload_inline: Optional[bytes]
    payload_ref: Optional[str]
    created_at: datetime
    updated_at: datetime

    def to_dict(self):
        return {
            "id": self.id, "type": self.job_type, "queue": self.queue, "state": self.state,
            "priority": self.priority, "run_at": isoformat(self.run_at), "attempts": self.attempts,
            "payload_size": self.payload_size, "created_at": isoformat(self.created_at),
            "updated_at": isoformat(self.updated_at),
        }


@dataclass
class Run:
    id: str
    job_id: str
    attempt: int
    owner: str
    state: str
    started_at: datetime
    lease_until: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    output: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id, "job_id": self.job_id, "attempt": self.attempt, "owner": self.owner,
            "state": self.state, "started_at": isoformat(self.started_at),
            "finished_at": isoformat(self.finished_at), "error": self.error,
        }
