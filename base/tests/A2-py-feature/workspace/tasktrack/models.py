"""Task records and their JSON form."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

PRIORITIES = ("low", "normal", "high")

_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


class ValidationError(ValueError):
    """A value given by the user or found in the store is not acceptable."""


def parse_date(text: str) -> date:
    """Parse a date written as YYYY-MM-DD."""
    match = _DATE.fullmatch(text.strip()) if isinstance(text, str) else None
    if match is None:
        raise ValidationError(f"invalid date {text!r}: expected YYYY-MM-DD")
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        raise ValidationError(f"invalid date {text!r}: no such day") from None


def format_date(value: date | None) -> str | None:
    """The stored form of a date; None stays None."""
    return value.isoformat() if value is not None else None


def normalize_tags(tags: Iterable[str]) -> list[str]:
    """Lower-case and strip tags, dropping blanks and repeats but keeping the order."""
    result: list[str] = []
    for tag in tags:
        cleaned = tag.strip().lstrip("#").lower()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


@dataclass
class Task:
    """One task. `due`, `created` and `completed` are calendar dates."""

    id: int
    title: str
    due: date | None = None
    priority: str = "normal"
    tags: list[str] = field(default_factory=list)
    done: bool = False
    created: date | None = None
    completed: date | None = None

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        if not self.title:
            raise ValidationError("a task needs a title")
        if self.priority not in PRIORITIES:
            raise ValidationError(f"unknown priority {self.priority!r}")
        self.tags = normalize_tags(self.tags)

    def complete(self, on: date) -> None:
        """Mark the task as done on the given day."""
        self.done = True
        self.completed = on

    def to_dict(self) -> dict[str, Any]:
        """The record as it is written to the store file."""
        return {
            "id": self.id,
            "title": self.title,
            "due": format_date(self.due),
            "priority": self.priority,
            "tags": list(self.tags),
            "done": self.done,
            "created": format_date(self.created),
            "completed": format_date(self.completed),
        }

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> Task:
        """Build a task from a record read from the store file."""
        if not isinstance(record, dict):
            raise ValidationError("a task record must be a JSON object")
        try:
            return cls(
                id=int(record["id"]),
                title=str(record["title"]),
                due=_stored_date(record.get("due")),
                priority=record.get("priority", "normal"),
                tags=list(record.get("tags") or []),
                done=bool(record.get("done", False)),
                created=_stored_date(record.get("created")),
                completed=_stored_date(record.get("completed")),
            )
        except ValidationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"malformed task record: {exc!r}") from None


def _stored_date(value: Any) -> date | None:
    return None if value is None else parse_date(value)
