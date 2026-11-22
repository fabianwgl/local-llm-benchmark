"""Command-line interface: python3 -m tasktrack [--file PATH] COMMAND ..."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import Sequence

from . import __version__
from .filters import SORT_KEYS, filter_tasks, is_overdue, sort_tasks
from .models import PRIORITIES, Task, ValidationError, parse_date
from .store import DEFAULT_PATH, Store, StoreError, TaskNotFound

EXIT_OK = 0
EXIT_ERROR = 2
TODAY_VARIABLE = "TASKTRACK_TODAY"


def current_date() -> date:
    """Today's date. TASKTRACK_TODAY=YYYY-MM-DD overrides the system clock."""
    override = os.environ.get(TODAY_VARIABLE)
    if override:
        return parse_date(override)
    return date.today()


def format_task(task: Task, today: date) -> str:
    """One line of `list` output."""
    if task.done:
        mark = "x"
    elif is_overdue(task, today):
        mark = "!"
    else:
        mark = " "
    due = task.due.isoformat() if task.due else "-"
    line = f"{task.id:>3} [{mark}] {due:<10} {task.priority:<6} {task.title}"
    for tag in task.tags:
        line += f" #{tag}"
    return line


def cmd_add(args: argparse.Namespace, store: Store) -> int:
    task = store.add(
        args.title,
        due=args.due,
        priority=args.priority,
        tags=args.tags,
        created=current_date(),
    )
    store.save()
    print(f"Added task {task.id}: {task.title}")
    return EXIT_OK


def cmd_list(args: argparse.Namespace, store: Store) -> int:
    tasks = filter_tasks(store.tasks, include_done=args.all, tag=args.tag, priority=args.priority)
    tasks = sort_tasks(tasks, args.sort)
    if not tasks:
        print("No tasks.")
        return EXIT_OK
    today = current_date()
    for task in tasks:
        print(format_task(task, today))
    return EXIT_OK


def cmd_done(args: argparse.Namespace, store: Store) -> int:
    task = store.get(args.id)
    if task.done:
        print(f"Task {task.id} is already done")
        return EXIT_OK
    task.complete(current_date())
    store.save()
    print(f"Completed task {task.id}: {task.title}")
    return EXIT_OK


def cmd_rm(args: argparse.Namespace, store: Store) -> int:
    task = store.remove(args.id)
    store.save()
    print(f"Removed task {task.id}: {task.title}")
    return EXIT_OK


def _date_argument(text: str) -> date:
    try:
        return parse_date(text)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tasktrack", description="A small command-line task tracker.")
    parser.add_argument("--version", action="version", version=f"tasktrack {__version__}")
    parser.add_argument(
        "--file", metavar="PATH", default=DEFAULT_PATH, help="store file (default: %(default)s)"
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    add = commands.add_parser("add", help="add a task")
    add.add_argument("title", metavar="TITLE")
    add.add_argument("--due", metavar="DATE", type=_date_argument, help="due date, YYYY-MM-DD")
    add.add_argument("--priority", choices=PRIORITIES, default="normal")
    add.add_argument(
        "--tag", dest="tags", metavar="TAG", action="append", default=[], help="may be given more than once"
    )
    add.set_defaults(handler=cmd_add)

    list_ = commands.add_parser("list", help="list tasks")
    list_.add_argument("--all", action="store_true", help="include completed tasks")
    list_.add_argument("--tag", metavar="TAG", help="only tasks with this tag")
    list_.add_argument("--priority", choices=PRIORITIES, help="only tasks with this priority")
    list_.add_argument("--sort", choices=SORT_KEYS, default="id")
    list_.set_defaults(handler=cmd_list)

    done = commands.add_parser("done", help="mark a task as completed")
    done.add_argument("id", metavar="ID", type=int)
    done.set_defaults(handler=cmd_done)

    rm = commands.add_parser("rm", help="delete a task")
    rm.add_argument("id", metavar="ID", type=int)
    rm.set_defaults(handler=cmd_rm)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit status."""
    args = build_parser().parse_args(argv)
    try:
        store = Store.load(args.file)
        return args.handler(args, store)
    except (ValidationError, StoreError, TaskNotFound) as exc:
        print(f"tasktrack: error: {exc}", file=sys.stderr)
        return EXIT_ERROR
