# Test catalog

Fifteen tests, 10 points each. "Scripted + judged" shows how the points split between automatic
checks and criteria judged by Claude. Each test's folder holds its prompt, files, hidden checks,
reference solution, and rubric; see `base/tests/README.md` for the layout. The public repository
contains only the prompt and the files the model receives.

## Agentic coding (45% of Core)

The model gets a repository in a sandbox, a ticket, and five tools. Hidden tests run afterwards.

| Test | Stack | The task | Scripted + judged |
|---|---|---|---|
| `A1-ts-bugfix` | TypeScript | Three customer reports of one-cent errors in an invoicing library: tax rounded per line, allocations that lose cents, negative halves rounding the wrong way | 8 + 2 |
| `A2-py-feature` | Python | Implement recurring tasks in a task-tracker CLI from a written spec: recurrence rules, month-end anchoring, catch-up, a store migration, error handling | 8 + 2 |
| `A3-rust-repair` | Rust | "CI is red": a borrow-checker error, a ring-buffer bug after wraparound, unimplemented functions, and behaviour that contradicts the README | 8 + 2 |
| `A4-ops-nightly` | Bash, SQL, make | A nightly job that fails on its second run and reports wrong numbers: migrations, quoting, line endings, a double-counting query, no fail-fast | 8 + 2 |
| `A5-ts-refactor` | TypeScript | Extract pricing logic duplicated across three handlers into one module without changing behaviour, although the three copies quietly differ | 8 + 2 |

Judged in these: whether the finish summary is truthful and names the real causes, and whether the
change is focused and well made.

## Single-shot engineering (30% of Core)

One prompt, one answer, no tools.

| Test | The task | Scripted + judged |
|---|---|---|
| `S1-code-review` | Review a password-reset pull request with eight planted defects and several decoys; findings as JSON with file, line, severity, and fix. False findings cost points | 4 + 6 |
| `S2-root-cause` | From an on-call note, a stack trace, a log excerpt, and four files, find why an endpoint fails in 60-second bursts, and decide whether the proposed revert would help | 3 + 7 |
| `S3-sql` | Four demanding SQLite queries (gap-filled monthly revenue with a moving average, a recursive referral-network rollup, an as-of join against a price history, longest purchase streak), each run on a visible and a hidden database | 10 + 0 |
| `S4-tools` | Eleven short tool-calling conversations under seven operating rules, with canned results: arithmetic over tool results, a replica limit, an ambiguous timeout, a long byte-exact payload, conditional action, error recovery, pagination, an instruction injected into tool output, strict JSON | 10 + 0 |

## Long-context (15% of Core)

| Test | The task | Scripted + judged |
|---|---|---|
| `L1-log-root-cause` | Find the cause of an incident in an hour of merged logs from five services (about 30,000 tokens), with exact times, the failed-request count, verbatim evidence, and the red herrings | 7 + 3 |
| `L2-codebase-qa` | Eight short-answer questions over a dump of an original 46-file job-scheduler codebase (about 30,000 tokens): each answer needs a trace across several files, and stopping one hop early gives a tempting wrong answer | 8 + 2 |

## General (10% of Core)

| Test | The task | Scripted + judged |
|---|---|---|
| `G1-meeting-notes` | Turn a 2,700-word meeting transcript into decisions, action items with owners and dates, and open questions. A decision is reversed, a task is reassigned, and some commitments are jokes | 4 + 6 |
| `G2-decision-memo` | A 350-word decision memo with a required structure, choosing between three ways to run a job exactly once. Judged on technical facts it must get right | 3 + 7 |

## Vision (reported separately)

Models without image input are marked n/a.

| Test | The task | Scripted + judged |
|---|---|---|
| `V1-terminal-screenshot` | Diagnose a failed `docker compose up` and a consequent migration error from a terminal screenshot | 6 + 4 |
| `V2-architecture-diagram` | Read a diagram of nine services and twelve arrows into nodes, directed edges, and arrow styles, then reason about a failure | 8 + 2 |

## Not a test

Before the tests, `run` measures generation speed with a fixed prompt (three runs, median). It is
reported on the scorecard and scores nothing.

## What the suite does not cover

Very large repositories, long multi-hour agent sessions, languages beyond the four stacks above,
front-end work that needs a browser, and anything requiring internet access.
