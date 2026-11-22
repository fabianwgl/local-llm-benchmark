from datetime import date

from tasktrack.filters import filter_tasks, sort_tasks
from tasktrack.models import Task


def make_tasks():
    return [
        Task(1, "Write report", due=date(2025, 4, 2), tags=["work"]),
        Task(2, "Book flights", due=date(2025, 3, 20), priority="high", tags=["travel"]),
        Task(3, "Tidy desk", priority="low", tags=["work"]),
        Task(4, "Renew passport", due=date(2025, 2, 10), tags=["travel"], done=True,
             completed=date(2025, 2, 8)),
    ]


def ids(tasks):
    return [task.id for task in tasks]


def test_done_tasks_are_hidden_unless_requested():
    assert ids(filter_tasks(make_tasks())) == [1, 2, 3]
    assert ids(filter_tasks(make_tasks(), include_done=True)) == [1, 2, 3, 4]


def test_filter_by_tag_and_priority():
    tasks = make_tasks()
    assert ids(filter_tasks(tasks, tag="work")) == [1, 3]
    assert ids(filter_tasks(tasks, tag="#Travel", include_done=True)) == [2, 4]
    assert ids(filter_tasks(tasks, priority="high")) == [2]
    assert ids(filter_tasks(tasks, tag="work", priority="high")) == []


def test_sort_orders():
    tasks = make_tasks()
    assert ids(sort_tasks(tasks, "due")) == [4, 2, 1, 3]
    assert ids(sort_tasks(tasks, "priority")) == [2, 1, 4, 3]
    assert ids(sort_tasks(reversed(tasks), "id")) == [1, 2, 3, 4]
