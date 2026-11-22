"""Selecting and ordering tasks for `list`."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from .models import PRIORITIES, Task

SORT_KEYS = ("id", "due", "priority")


def is_overdue(task: Task, today: date) -> bool:
    """True for an open task whose due date has passed."""
    return not task.done and task.due is not None and task.due < today


def filter_tasks(
    tasks: Iterable[Task],
    *,
    include_done: bool = False,
    tag: str | None = None,
    priority: str | None = None,
) -> list[Task]:
    """The tasks that meet every given condition, in their original order."""
    wanted_tag = tag.strip().lstrip("#").lower() if tag else None
    selected = []
    for task in tasks:
        if task.done and not include_done:
            continue
        if wanted_tag is not None and wanted_tag not in task.tags:
            continue
        if priority is not None and task.priority != priority:
            continue
        selected.append(task)
    return selected


def sort_tasks(tasks: Iterable[Task], key: str = "id") -> list[Task]:
    """Order tasks for display.

    id        by id
    due       earliest due date first, tasks without a due date last, then by id
    priority  high, normal, low, then by id
    """
    if key == "id":
        return sorted(tasks, key=lambda task: task.id)
    if key == "due":
        return sorted(tasks, key=lambda task: (task.due is None, task.due or date.min, task.id))
    if key == "priority":
        return sorted(tasks, key=lambda task: (-PRIORITIES.index(task.priority), task.id))
    raise ValueError(f"unknown sort key {key!r}")
