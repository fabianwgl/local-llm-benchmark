# How a test is built

Every test is a folder `base/tests/<ID>-<slug>/`. Worked examples to copy from:
`A1-ts-bugfix` (agentic), `S3-sql` (single-shot), `S4-tools` (sub-cases).

In the public repository a test folder holds only what the model is given: `prompt.md`,
`workspace/`, and `input/`. `test.json`, `rubric.md`, and `hidden/` are kept private, because they
contain the answers.

```
<test>/
├── test.json     # metadata, limits, check command, scoring
├── prompt.md     # exactly what the model is told ({{include:PATH}} inlines a file from the test folder)
├── rubric.md     # answer key + judge criteria with levels; never shown to the model
├── workspace/    # agentic: the repository copied to /work in the sandbox
├── input/        # single-shot: files included into the prompt, or images
└── hidden/       # never shown to the model
    ├── check.py          # the scripted check (runs in a fresh container as root)
    ├── overlay/          # optional: files laid over the model's final tree before checking
    └── reference/        # a solution that must earn every scripted point
        ├── workspace/    # agentic: files laid over workspace/ to form the reference solution
        ├── delete.txt    # agentic, optional: paths the reference solution removes
        ├── response.md   # single-shot: the reference answer; agentic: a reference finish summary
        └── baseline.md   # single-shot, optional: a plausible wrong answer (default: empty answer)
```

## test.json

```json
{
  "id": "A1-ts-bugfix",
  "title": "Fix three rounding defects in a TypeScript invoicing library",
  "category": "agentic",                 // agentic | swe | long | general | vision
  "mode": "agentic",                     // agentic | single | cases
  "requires": ["tools"],                 // "vision" marks the test n/a for models without image input
  "prompt": "prompt.md",
  "workspace": "workspace",              // agentic only
  "protected": ["test", "README.md"],    // agentic: fixture files the model must not edit or delete
  "env": {"TZ": "UTC"},                  // optional: environment for the sandbox and the check
  "inputs": [{"path": "input/x.png", "kind": "image"}],   // single-shot images
  "check": {"cmd": "python3 /hidden/check.py", "timeout_s": 300},
  "score": {
    "max": 10,
    "checks": {"some_check": 2.5, "gated": {"points": 1, "requires": "some_check"}},
    "judge": [{"id": "criterion_id", "max": 1, "step": 0.5, "text": "One-sentence criterion."}]
  },
  "selftest": {"baseline_max": 1.5},
  "version": 1
}
```

- Scripted points plus judge points add up to `score.max` (always 10).
- A check value is `true`/`false` or a fraction between 0 and 1 (partial credit).
- `requires` makes one check count only if another is truthy. Use it so that doing nothing cannot earn
  points for things that were already true in the fixture.
- A judge criterion may have a negative range for penalties: `{"id": "...", "min": -2, "max": 0, "step": 0.5}`.

## The check

`check.cmd` runs in a fresh container (no network) as root. The runner copies in, never mounts:

| Path | Content |
|---|---|
| `/in/response.md` | the model's answer (single-shot) or its finish summary (agentic) |
| `/in/workspace/` | the model's final tree (agentic); edited or deleted `protected` files already restored |
| `/in/cases.json` | recorded sub-case transcripts (cases mode) |
| `/in/meta.json` | `{test, end_reason, tampered}` |
| `/hidden/` | the test's `hidden/` folder |
| `/checklib/checklib.py` | shared helpers (`base/tests/_lib/checklib.py`) |

The check writes its outcome with `checklib.result({"check_id": value, ...}, notes={...})`.
Rules:

- Run model-written code only through `checklib.run(...)` or the `node_tests` / `pytest_tests` /
  `cargo_tests` helpers. They execute as the unprivileged `bench` user, so model code cannot touch `/out`.
- Start with `checklib.prepare_workspace(overlay="overlay")`, which copies `/in/workspace` to `/tmp/w`
  and lays hidden test files over it.
- Grade against the expected list of test names (`group_fraction`), so a hidden test file that fails
  to load scores zero instead of silently shrinking the denominator.
- Parse answers leniently (`extract_json`, `fenced_blocks`, `trailer`) unless strict formatting is
  the thing being tested. Never fail a model for formatting trivia the prompt did not ask for.
- Put useful detail in `notes`; the judge and the analysis read it.

## Design rules

1. **The spec is in the workspace or the prompt.** Hidden checks only test behaviour that the
   prompt, README, or a spec document states. If two reasonable engineers could disagree about the
   right answer, the spec is not finished.
2. **No hints.** Fixture code must not contain comments that point at planted defects, and names
   must not give them away. Fixtures should read like ordinary code written by a competent team.
3. **No third-party dependencies.** Node's built-in test runner on `.ts` sources, Python's standard
   library plus pytest, Rust `std`, sqlite3, bash. Everything must work with no network.
4. **The untouched fixture's own tests pass.** A model that runs the visible tests first must see green.
5. **Partial credit.** Prefer several independent check groups over one all-or-nothing check, so
   results spread: a weak model should land well below a strong one, and neither at 0 or 10.
6. **Doing nothing scores (almost) nothing.** Set `selftest.baseline_max` to what the untouched
   fixture earns and keep it small.
7. **Deterministic.** No randomness, wall-clock dependence, or host dependence in checks. Generated
   data is generated once and committed.
8. **Canary.** `rubric.md` and every text file under `hidden/` carries the suite's canary string
   (see `base/suite.json`) in a comment. The runner aborts if it ever appears in a request.
9. **Judge criteria are small and checkable.** Each has fixed levels with a one-line description per
   level in `rubric.md`, and must be decidable from the packet (response, diff, check results).

## Verifying a test

```
python3 base/runner/bench.py selftest --tests <ID>
```

must print `reference ok` (every scripted point earned) and `baseline ok` (the untouched fixture, or
the baseline answer, earns at most `baseline_max`).

Sandbox image (`llm-bench-sandbox:1`): Node 24 with `tsc` 5.9 and `npm`, Python 3.11 with pytest 7.2,
Rust/cargo 1.100, sqlite 3.40, shellcheck 0.9, git, ripgrep, jq, make. Model commands run as user
`bench` in `/work` with no network, 2 GB of memory, and a 120-second limit per command.
