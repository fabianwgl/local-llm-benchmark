# Running the benchmark

For the maintainer. Running and scoring need the private test definitions and checks, which are not
in the public repository (see the README).

## Requirements

- LM Studio with its local server running on port 1234 (`lms server start`).
- Docker Desktop running (agentic tests and all checks run in a sandbox container).
- `python3` (3.9 or newer). No packages to install.

One-time setup: `python3 base/runner/bench.py sandbox-build`

## Benchmarking a model

All commands are run from the repository root. `B` below stands for `python3 base/runner/bench.py`.

```
B models                                   # what LM Studio has, and each model's folder name
B probe --model qwen/qwen3.8-27b           # optional: record how it behaves over the API
B run --model qwen/qwen3.8-27b --unload    # run every test, one by one
B status                                   # what has run, and what still needs judging
```

`run` loads the model alone with the suite's fixed settings, runs a short speed probe, then each
test in turn. It skips tests that already have a result, so a stopped run continues where it left
off. Useful options: `--tests A1,S3` for a subset, `--seeds 1,2` for a second run of every test,
`--reasoning none` to test the same model with reasoning off (that becomes its own row).

A full run takes hours, and the machine is busy while it runs. Run one model at a time.

## Judging and reading the results

The models are run by hand; Claude judges. Ask Claude Code, in this folder, to "judge the pending
runs". It follows `EVALUATION.md`:

```
B packet                             # blind packets under judging/<batch>/
(Claude judges each packet itself, in the session)
B score --judge-model <judge id>     # validates verdicts, writes the reports
```

Judging works best once two or more models have runs waiting, so that the anonymous packets stay
anonymous.

`B score` writes `LEADERBOARD.md`, every `models/<slug>/SCORECARD.md` (points only, published) and
`EVIDENCE.md` (the same with the judge's reasons and quotes, kept private), and the results block in
`README.md` (between the `results:start` and `results:end` markers). It can be run at any time;
before judging it shows provisional, scripted-only scores.

## Other commands

```
B selftest             # prove every check works, with no model involved (run after editing a test)
B check                # re-apply scripted checks to saved output (automatic when grading changed)
```

`base/runner/notify.py` is an optional send-only Telegram notifier for long runs. It reads
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from the environment or from `.env` (see `.env.example`).

## Publishing

The repository is public. `.gitignore` keeps the answer keys and raw runs out of it: each test's
`hidden/`, `rubric.md` and `test.json`, everything under `models/*/runs/` except `run.json`, every
`models/*/EVIDENCE.md`, the `judging/` folder, and `.env`. Never force-add any of these. After judging, commit the regenerated
reports and the new `ANALYSIS.md` files and push.

## Good to know

- Scores from one run per test carry a few points of noise. The MLX engine ignores the seed, so
  its runs cannot be replayed exactly. Small gaps are ties.
- Do not update LM Studio in the middle of a comparison. Versions are recorded per model and the
  leaderboard flags mismatches.
- The two largest models need about 27 GB at the suite's context length. Close other heavy apps;
  the scorecard flags runs during which the system started swapping.
- To add or change a test, see `base/tests/README.md`.
