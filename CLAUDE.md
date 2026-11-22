# Local LLM benchmark (LM Studio)

A benchmark of local models served by LM Studio on this Mac. The user runs the models; you
(Claude) judge the results and write the analysis. Start with `README.md` and
`base/docs/RUNNING.md`.

## Commands (run from this folder)

```
python3 base/runner/bench.py models | probe | run | status | check | selftest | packet | score
```

- Run a model: `bench.py run --model <lm-studio-key> --unload` (hours; one model at a time;
  resumable). The user starts runs. Give them the command; start one yourself only if they ask.
- Judge: follow `base/docs/EVALUATION.md` exactly: `packet`, judge every packet yourself in this
  session, then `score --judge-model <id>`. Afterwards write `models/<slug>/ANALYSIS.md`.
- After editing any test: `bench.py selftest` must pass.

## Hard rules

- Never edit `LEADERBOARD.md`, `SCORECARD.md`, `scores.json`, `check.json`, `run.json`, or
  `verdict.json` by hand, nor the block between the `results:start` and `results:end` markers in
  `README.md`. They are generated. Fix the input and regenerate.
- Never re-run a test because its score was low. Re-run only after an infrastructure failure.
- Do not spawn subagents in this project. All work, judging included, happens in the main session.
- Do not start `bench.py run` or `bench.py probe` unless the user asks for it in this conversation.
  A run ties up their Mac for hours.
- Judging is blind: while judging, do not open `judging/*/map.json` or anything under `models/`.
- Never put anything from a test's `hidden/` folder or `rubric.md` into a prompt for a local model.
- While `base/suite.json` says `"frozen": true`, do not change a test's prompt, files, or limits
  without the user's agreement: it invalidates every existing run of that test.
- This folder is a public git repository. `.gitignore` keeps the answer keys and raw runs out
  (`hidden/`, `rubric.md`, `test.json`, `models/*/runs/` except `run.json`, `judging/`, `.env`). Never
  force-add them, and never copy their content into a tracked file. `ANALYSIS.md` is public: describe
  how a model failed without spelling out a test's expected answer.
- One model in memory at a time. Do not load models by hand while a run is in progress.

## Where things are

- `base/suite.json`: fixed settings, budgets, weights. `base/docs/`: methodology, test catalog, judging protocol.
- `base/tests/<id>/`: one test each; `base/tests/README.md` explains the layout.
- `base/runner/`: `bench.py` (CLI), `lmstudio.py` (client), `agent.py` (tool loop, sandbox), `report.py` (packets, scores, reports).
- `models/<slug>/`: `model.json`, `probe.json`, `runs/`, `SCORECARD.md`, `ANALYSIS.md`.
