# tasktrack

A small command-line task tracker. All tasks live in one JSON file. It needs Python 3.9 or newer
and nothing outside the standard library.

## Usage

```
python3 -m tasktrack [--file PATH] COMMAND [options]
```

`--file PATH` names the store file and comes before the command. The default is `tasks.json` in
the current directory. A store file that does not exist yet is an empty store.

| Command | Effect | Prints |
|---|---|---|
| `add TITLE [--due DATE] [--priority P] [--tag TAG]...` | adds a task | `Added task 3: TITLE` |
| `list [--all] [--tag TAG] [--priority P] [--sort KEY]` | lists tasks | one line per task |
| `done ID` | marks a task as completed | `Completed task 3: TITLE` |
| `rm ID` | deletes a task | `Removed task 3: TITLE` |

- Dates are written `YYYY-MM-DD`.
- Priorities are `low`, `normal` (the default) and `high`.
- Tags are stored in lower case; `--tag` may be given more than once.
- Ids count up from 1 and are never reused, not even after `rm`.
- `done` on a task that is already done prints `Task 3 is already done`, exits with status 0 and
  changes nothing.

### `list`

```
$ python3 -m tasktrack list --all
  1 [!] 2025-03-01 high   Pay rent #home #bills
  2 [ ] -          normal Call plumber
  3 [x] 2025-02-10 low    Renew passport #travel
```

Each line shows the id, the state (`[ ]` open, `[!]` open and overdue, `[x]` done), the due date
or `-`, the priority, the title and the tags. Completed tasks are only listed with `--all`.
`--tag` and `--priority` narrow the list. `--sort` takes `id` (the default), `due` (earliest
first, tasks without a due date last) or `priority` (high first). When nothing matches, `list`
prints `No tasks.`

### Exit status and errors

The exit status is 0 on success and 2 on any error: an id that no task has, a date that does not
exist, an unknown option or value, a store file that cannot be read. Errors are reported on
stderr, nothing is printed to stdout, and the store file is left as it was.

### The current date

The current date is used for `created`, for `completed` and for the overdue mark. Setting the
environment variable `TASKTRACK_TODAY=YYYY-MM-DD` overrides the system clock; the tests use it.

## Store file

```json
{
  "version": 1,
  "next_id": 4,
  "tasks": [
    {
      "id": 1,
      "title": "Pay rent",
      "due": "2025-03-01",
      "priority": "high",
      "tags": ["home", "bills"],
      "done": false,
      "created": "2025-02-20",
      "completed": null
    }
  ]
}
```

`due` and `completed` are `null` when they have no value. `next_id` is the id the next new task
gets. The file is replaced atomically on every change (it is written to a temporary file that is
then renamed), and a file with any other `version` is rejected.

## Development

```
python3 -m pytest -q
```

| Module | Responsibility |
|---|---|
| `tasktrack/cli.py` | argument parsing, the four commands, output |
| `tasktrack/store.py` | reading and writing the store file |
| `tasktrack/models.py` | the task record, dates, validation |
| `tasktrack/filters.py` | selecting and sorting tasks for `list` |

Specifications for larger changes are kept in `docs/`.
