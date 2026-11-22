# finance-nightly runbook

The nightly job loads the web shop's order exports into a SQLite database and writes the daily
revenue report that finance reconciles against the payment provider every morning.

- Owner: data-platform on-call
- Host: `batch-01`, checkout in `/srv/finance-nightly`
- Cron: `30 2 * * *` (UTC), command `cd /srv/finance-nightly && make nightly`
- Needs: bash, sqlite3 3.40 or newer, GNU make. Nothing else is installed on batch-01.

## Commands

| Command | What it does |
|---|---|
| `make nightly` | runs `bin/nightly.sh`: migrations, import, report |
| `make clean` | deletes `var/` and `out/` (local development only, never on batch-01) |

## Layout

| Path | Content |
|---|---|
| `bin/nightly.sh` | the job |
| `migrations/NNN_<name>.sql` | schema migrations |
| `sql/report.sql` | the report query |
| `incoming/` | exports dropped by the shop's export tool, and on bad days by hand |
| `var/nightly.db` | the database; all job state lives under `var/` |
| `out/report.csv` | the report |
| `logs/` | output of failed cron runs |

## What a run does

A run has three steps, always in this order: migrations, import, report.

- **Fail fast.** Any step that fails aborts the job at once with a non-zero exit code and a message
  on stderr; nothing after it runs. A run that exits 0 has completed all three steps.
- **Safe to rerun.** Running the job again with the same `incoming/` leaves the database and the
  report exactly as they were.
- **Persistent database.** The job never deletes or recreates `var/nightly.db`. Exports are pruned
  from `incoming/` after 30 days by a separate housekeeping job, and their rows must stay.

### 1. Migrations

- Every file `migrations/NNN_<name>.sql` is a migration. They are applied in order of file name.
- Each migration is applied exactly once per database. Applied migrations are recorded in the table
  `schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)`, where `version` is the
  file name without `.sql` (for example `001_init`) and `applied_at` is the UTC time it was applied.
  A run applies only the migrations that are not recorded yet.
- A migration that fails aborts the job and is not recorded.

### 2. Import

Every run imports every `*.csv` file in `incoming/`, in byte order of file name (as `LC_ALL=C ls`
sorts them). The job never moves, renames or deletes files in `incoming/`.

The file name decides the table; any other `.csv` file name is an error:

| File name | Header line (exactly) | Table |
|---|---|---|
| `orders_*.csv` | `order_id,ordered_on,customer,channel,shipping_cents,status` | `orders` |
| `items_*.csv` | `order_id,line_no,sku,description,qty,unit_price_cents` | `order_items` |

Each field is stored in the table column of the same name, and `source_file` is set to the name of
the file the row was imported from (without the directory). Values:

- `ordered_on` is a date `YYYY-MM-DD`; `channel` is `web`, `marketplace` or `phone`.
- `status` is `paid`, `pending`, `cancelled` or `refunded`.
- `shipping_cents`, `line_no`, `qty` and `unit_price_cents` are whole numbers (cents are euro cents).

**Keys.** Imports are keyed: an order is identified by `order_id`, an item row by
(`order_id`, `line_no`). A key appears at most once within a file. When an imported row's key is
already in the database, the imported row replaces the stored one. So re-importing a file changes
nothing, and when the shop sends a corrected re-export (it sorts after the original), the
correction wins.

**Input conventions.** The export tool and the people who export by hand produce all of these:

- UTF-8, comma-separated, the header on the first line, no blank lines.
- A field that contains a comma or a double quote is enclosed in double quotes, and a double quote
  inside it is written `""` (RFC 4180). Quoted fields never contain line breaks.
- Lines end in LF or in CRLF (exports made on the Windows workstation in the warehouse use CRLF).
  The last line may lack a line ending.
- File names may contain spaces; manual exports are named like `orders_2025-03-03 manual export.csv`.

**Malformed files.** A file is malformed if

1. its header line is not exactly the header for its kind, or
2. a row has a different number of fields than the header (an unquoted comma, a missing value), or
3. a value in `shipping_cents`, `line_no`, `qty` or `unit_price_cents` is not written with digits
   only (`12.50`, `-3` and an empty value are malformed).

A malformed file is a failing step: the job aborts with a non-zero exit code.

### 3. Report

Every successful run rewrites `out/report.csv` with the result of `sql/report.sql`, as written by
`sqlite3 -header -csv`. It has a header line and one row per day and channel with at least one
paid order:

| Column | Meaning |
|---|---|
| `day` | the orders' `ordered_on` |
| `channel` | the orders' `channel` |
| `orders` | number of paid orders |
| `items` | sum of `qty` over the item rows of those orders |
| `revenue_cents` | sum over those orders of the order's item amounts (`qty × unit_price_cents` for each item row) plus the order's `shipping_cents`, which counts once per order |

Only orders with status `paid` count. Rows are sorted by `day`, then `channel`. Every order in the
exports has at least one item row.

## When it fails

- cron mails the output of a failed run to on-call; the output of the last failed run is kept in
  `logs/last_failure.log`.
- Fix the cause, then run `make nightly` again. A rerun is always safe (see above).
- Finance reads `out/report.csv` at 08:00 UTC. If it is not there by then, tell #finance-ops.
