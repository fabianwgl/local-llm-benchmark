# Specification: recurring tasks

This document is the contract for recurring tasks and for version 2 of the store file. Anything
it does not mention keeps working as described in `README.md`.

A *date* is written `YYYY-MM-DD`. *Today* is the current date as the program already determines
it: `TASKTRACK_TODAY` if that environment variable is set, otherwise the system clock. Every rule
below that mentions today uses this value.

## 1. `add --every` and `--until`

```
python3 -m tasktrack add TITLE --due DATE --every RECURRENCE [--until DATE] [other options]
```

- `--every` makes the new task recurring. `RECURRENCE` is one of `daily`, `weekdays`, `weekly`
  and `monthly`. `--every` can only be used together with `--due`.
- `--until DATE` sets the last date on which the series may have a task due (section 3.3). It
  can only be used together with `--every`, and `DATE` must not be earlier than the `--due`
  date (it may be the same date).
- The task is stored with these fields (section 5 has the full record):
  - `recurrence`: the `RECURRENCE` word;
  - `anchor_day`: for `monthly`, the day of the month of the due date (an integer from 1 to
    31); for the other three, `null`;
  - `until`: the `--until` date, or `null` without `--until`.
- A task added without `--every` is stored with `recurrence`, `anchor_day` and `until` all
  `null`.
- What `add` prints does not change.

## 2. `done` on a recurring task

When `done ID` completes an open task whose `recurrence` is not `null`, one save does both of
the following:

1. The task is completed as before: `done` becomes `true` and `completed` becomes today.
2. Unless the series has ended (section 3.3), a new task, the *successor*, is added:

   | Field | Value |
   |---|---|
   | `id` | the store's `next_id`, which then goes up by one, as for `add` |
   | `title`, `priority`, `tags`, `recurrence`, `anchor_day`, `until` | copied from the completed task |
   | `due` | the next due date (section 3) |
   | `created` | today |
   | `done`, `completed` | `false`, `null` |

When a successor is added, the command prints two lines to stdout:

```
Completed task 3: Pay rent
Next: task 4 due 2025-04-30
```

When the series has ended, it prints only the first line, and `next_id` does not change.

Nothing else creates a successor: not `done` on a task without a recurrence, not `rm`, and not
`done` on a task that is already done. That last case behaves as before for every task: it
prints `Task 3 is already done`, exits with status 0, creates nothing and does not save the
store.

## 3. The next due date

### 3.1 Occurrences

Each recurrence defines which dates are *occurrences* of the series:

| `recurrence` | occurrences |
|---|---|
| `daily` | every date |
| `weekdays` | every Monday, Tuesday, Wednesday, Thursday and Friday |
| `weekly` | every date a whole number of weeks before or after the task's due date (so always the same weekday as the due date) |
| `monthly` | one date in every month: day `anchor_day` of that month, or the last day of the month if the month has fewer days than `anchor_day` |

`anchor_day` never changes along a series, so a monthly series that had to fall back to the end
of a short month returns to its day in the next month that has it: anchor day 31 gives
2025-01-31, 2025-02-28, 2025-03-31, 2025-04-30. Leap years follow the Gregorian calendar: 2000
and 2024 have a 29 February, 2025 and 2100 do not.

### 3.2 Which occurrence is next

The next due date is **the first occurrence that is strictly later than both the task's due
date and today**.

- A task completed on or before its due date: the next due date is the first occurrence after
  the due date. It is worked out from the due date, not from today: a weekly task due
  2025-03-10 that is completed on 2025-03-01 gets a successor due 2025-03-17.
- A task completed late (today is after its due date): the series catches up. Occurrences up to
  and including today are skipped, and no task is created for them; the successor is due on the
  first occurrence after today. The series keeps its rhythm: a weekly task due Monday
  2025-03-03 that is completed on Wednesday 2025-03-12 gets a successor due Monday 2025-03-17,
  not 2025-03-10 and not 2025-03-19.

| `recurrence` | `anchor_day` | `due` | today | next due date |
|---|---|---|---|---|
| `daily` | `null` | 2024-02-28 | 2024-02-28 | 2024-02-29 |
| `daily` | `null` | 2025-03-10 | 2025-03-05 | 2025-03-11 |
| `daily` | `null` | 2025-03-10 | 2025-03-14 | 2025-03-15 |
| `weekdays` | `null` | 2025-03-06 | 2025-03-06 | 2025-03-07 |
| `weekdays` | `null` | 2025-03-07 | 2025-03-07 | 2025-03-10 |
| `weekly` | `null` | 2025-12-29 | 2025-12-29 | 2026-01-05 |
| `weekly` | `null` | 2025-03-03 | 2025-03-10 | 2025-03-17 |
| `monthly` | 31 | 2025-01-31 | 2025-01-31 | 2025-02-28 |
| `monthly` | 31 | 2025-02-28 | 2025-02-20 | 2025-03-31 |
| `monthly` | 31 | 2024-01-31 | 2024-01-31 | 2024-02-29 |
| `monthly` | 31 | 2025-12-31 | 2025-12-31 | 2026-01-31 |
| `monthly` | 31 | 2025-01-31 | 2025-03-15 | 2025-03-31 |

### 3.3 The end of a series

When `until` is not `null`, the series ends there: if the next due date is later than `until`,
no successor is created and the completed task is the last one of the series. A next due date
equal to `until` still gets a successor. Because the next due date includes the catch-up of
section 3.2, completing a task late can end a series that completing it on time would have
continued.

## 4. `list`

- New option `--due-before DATE`: only tasks whose due date is strictly earlier than `DATE` are
  listed. A task due on `DATE` itself is not listed, and neither is a task without a due date.
  The option is one more condition next to the existing ones, so completed tasks still need
  `--all`, and `--tag`, `--priority` and `--sort` keep working with it.
- The line of a recurring task, open or completed, ends with a space and its recurrence in
  parentheses, after any tags: `  4 [ ] 2025-04-30 high   Pay rent #home (monthly)`. Other
  lines do not change.

## 5. Store file, version 2

```json
{
  "version": 2,
  "next_id": 5,
  "tasks": [
    {
      "id": 4,
      "title": "Pay rent",
      "due": "2025-04-30",
      "priority": "high",
      "tags": ["home"],
      "done": false,
      "created": "2025-03-31",
      "completed": null,
      "recurrence": "monthly",
      "anchor_day": 31,
      "until": "2025-12-31"
    }
  ]
}
```

Version 2 differs from version 1 in `"version": 2` and in three more task fields:

| Field | Value |
|---|---|
| `recurrence` | `"daily"`, `"weekdays"`, `"weekly"`, `"monthly"` or `null` |
| `anchor_day` | an integer from 1 to 31 for a monthly task, otherwise `null` |
| `until` | a date string or `null` |

- **Writing.** Every save writes version 2, and every task record has all eleven fields shown
  above. Saving stays atomic, and afterwards there is no other file next to the store file (no
  backup, no temporary file).
- **Reading.** Version 1 and version 2 files are accepted; any other version is rejected as
  before. A task record without `recurrence`, `anchor_day` or `until` is read as if the field
  were `null`. A monthly task whose `anchor_day` is `null` is read as if `anchor_day` were the
  day of its `due` date. A record whose `recurrence` is not one of the four words or `null`, or
  that has a recurrence but no due date, makes the file unusable like any other malformed
  record.
- **Migration.** There is no migration command. A version 1 file becomes a version 2 file the
  first time a command saves the store. A command that saves nothing (`list`, `done` on a task
  that is already done, any command that fails) leaves the file byte for byte as it was, also
  when it is a version 1 file.
- **Unknown fields.** Other tools keep their own data in the store file. Every key that this
  document and `README.md` do not define, at the top level or inside a task record, in a
  version 1 or a version 2 file, is kept with its value unchanged (whatever JSON value it is)
  whenever the store is saved. A successor does not inherit the unknown fields of the task it
  follows.

## 6. Errors

Each of these exits with status 2, prints a message to stderr and nothing to stdout, and leaves
the store file as it was:

- `--every` with a value other than `daily`, `weekdays`, `weekly` or `monthly`;
- `--every` without `--due`;
- `--until` without `--every`, or with a date earlier than the `--due` date;
- a `--due`, `--until` or `--due-before` value that is not an existing date in the form
  `YYYY-MM-DD` (`2025-02-30` and `2023-02-29` are not dates);
- `done` or `rm` with an id that no task has;
- a store file with an unsupported version or an unusable task record.

The wording of the messages is up to the implementation.

## 7. Also part of this change

- `README.md` describes the new options, the next-due-date rules and the version 2 store file.
- New behaviour is covered by tests. The existing tests keep passing without being edited.
