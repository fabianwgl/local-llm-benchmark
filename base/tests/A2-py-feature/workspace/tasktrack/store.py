"""The JSON file that holds the tasks."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator

from .models import Task, ValidationError

SCHEMA_VERSION = 1
DEFAULT_PATH = "tasks.json"


class StoreError(Exception):
    """The store file cannot be read or written."""


class TaskNotFound(LookupError):
    """No task has the requested id."""

    def __init__(self, task_id: int) -> None:
        super().__init__(f"no task with id {task_id}")
        self.task_id = task_id


class Store:
    """The tasks of one store file and the id the next new task will get."""

    def __init__(self, path: str | os.PathLike[str], tasks: Iterable[Task] = (), next_id: int = 1) -> None:
        self.path = Path(path)
        self.tasks: list[Task] = list(tasks)
        self.next_id = next_id

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> Store:
        """Read the store file. A file that does not exist yet is an empty store."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls(path)
        except (OSError, UnicodeDecodeError) as exc:
            raise StoreError(f"cannot read {path}: {exc}") from None
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise StoreError(f"{path} is not valid JSON ({exc})") from None
        if not isinstance(data, dict) or not isinstance(data.get("tasks", []), list):
            raise StoreError(f"{path} is not a task store")
        version = data.get("version")
        if version != SCHEMA_VERSION:
            raise StoreError(f"{path} has store version {version!r}, expected {SCHEMA_VERSION}")
        try:
            tasks = [Task.from_dict(record) for record in data.get("tasks", [])]
            next_id = int(data.get("next_id", 1))
        except (ValidationError, TypeError, ValueError) as exc:
            raise StoreError(f"{path}: {exc}") from None
        highest = max((task.id for task in tasks), default=0)
        return cls(path, tasks, max(next_id, highest + 1))

    def save(self) -> None:
        """Write the store file atomically: a temporary file is written, then renamed into place."""
        payload = {
            "version": SCHEMA_VERSION,
            "next_id": self.next_id,
            "tasks": [task.to_dict() for task in self.tasks],
        }
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise StoreError(f"cannot write {self.path}: {exc.strerror or exc}") from None

    def add(
        self,
        title: str,
        *,
        due: date | None = None,
        priority: str = "normal",
        tags: Iterable[str] = (),
        created: date | None = None,
    ) -> Task:
        """Create a task with the next free id and append it."""
        task = Task(id=self.next_id, title=title, due=due, priority=priority, tags=list(tags), created=created)
        self.tasks.append(task)
        self.next_id += 1
        return task

    def get(self, task_id: int) -> Task:
        """The task with the given id."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise TaskNotFound(task_id)

    def remove(self, task_id: int) -> Task:
        """Delete a task and return it. Its id is not handed out again."""
        task = self.get(task_id)
        self.tasks.remove(task)
        return task

    def __iter__(self) -> Iterator[Task]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)
