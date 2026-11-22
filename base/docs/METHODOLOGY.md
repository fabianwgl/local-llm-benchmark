# Methodology

This benchmark compares local language models as they are actually served by LM Studio on one
machine, on work a software engineer does every day. It answers two questions: which of my local
models should I use, and how far can I trust it?

## What one result means

A leaderboard row is **one configuration**: a model, at one quantisation, at one reasoning level,
served by LM Studio's local server on this Mac. The folder name carries all three, for example
`qwen3.8-27b__mlx-4bit__r-xhigh`. The same model at another quantisation or with reasoning switched
off is a different row.

Results are comparable only within one suite version (`base/suite.json`) and, strictly, one LM
Studio and engine version. Each scorecard records the versions it was produced on, and the
leaderboard flags rows that differ.

## Fixed conditions

Every model is run under the same conditions, all defined in `base/suite.json`.

| Condition | Value | Why |
|---|---|---|
| Models in memory | Exactly one, loaded by the runner | Memory pressure would distort speed and can change behaviour |
| Context length | 80,000 tokens, requested explicitly | Matches the LM Studio default on this machine; llama.cpp rounds it up to 80,128 |
| Parallel slots | 1 | More slots split the context on some engines |
| Endpoint | `POST /v1/chat/completions`, streamed | The one endpoint that carries text, tools, and images for every engine |
| Sampler | temperature 0.6, top_p 0.95, top_k 20, repeat penalty off | One explicit sampler for all, recorded with every run. Greedy decoding makes reasoning models loop |
| Reasoning | Each model's shipped level | It is how the model is normally used. The level is part of the row's identity |
| System prompt | One fixed prompt per test mode | So that no model gets extra hints |
| Independence | Fresh conversation and fresh files for every test | No test can leak into the next |

**Budgets.** Every model gets the same output budget, thinking included: 16,384 tokens for a
single-shot answer; for an agentic test, 40 steps of at most 8,192 tokens and 48,000 output tokens
in total. Running out is a recorded outcome that is scored on what was delivered. It is never
retried with more. Wall-clock limits (90 minutes agentic, 30 minutes single-shot) exist only as a
safety net, so that speed is not scored as quality.

**Runs.** The default is one run per test. A second run is one command (`--seeds 1,2`); the score
is then the mean and the spread is shown. A test is re-run only after an infrastructure failure,
never because the score was low, and every run is kept.

## What the server really does

`bench.py probe` records how each model behaves over the API (`models/<slug>/probe.json`). These
findings shaped the design:

- **The seed is honoured by the llama.cpp engine (GGUF) and ignored by the MLX engine.** An MLX run
  is a sample, not a replay. With one run per test, expect a few points of noise.
- **Reasoning can be switched off** with `reasoning_effort: "none"`, although LM Studio does not
  document it for this endpoint. `bench.py run --reasoning none` uses it to create a separate row.
- **`response_format` is not used in scored tests.** With reasoning on, the MLX engine puts the
  constrained JSON into the reasoning channel and returns an empty answer. That is an engine quirk,
  not a model skill, so structured output is tested by instruction instead.
- **A prompt that does not fit returns an explicit error**; history is not silently truncated. The
  runner still stops an agentic run before the window is full, and voids an attempt if the server's
  prompt-token count ever shrinks between steps.
- Usage is reported in the stream, including reasoning tokens. Image tokens are not counted by the
  MLX engine.

## The agentic harness

Agentic tests give the model a repository and a ticket, and five tools: `read_file`, `write_file`,
`edit_file`, `run_command`, and `finish`. The harness is deliberately minimal and identical for
every model, so the result reflects the model and not a product's scaffolding.

- **Sandbox.** One Docker container per test, built from `base/runner/sandbox/Dockerfile`: no
  network, 2 GB of memory, an unprivileged user. Files are copied in; nothing on the host is
  mounted, and every tool call executes inside the container.
- **Ending.** A run ends when the model calls `finish` or exhausts a budget. A reply without a tool
  call gets one fixed nudge, at most two in a row and six per test, because weaker models often
  describe a plan and stop.
- **Tool-call errors.** Invalid JSON arguments, unknown tools, and missing arguments come back as
  an error the model can read. Text that merely looks like a tool call is not executed. All of it
  is counted and reported as tool-call validity; the harness never repairs a call.

| A run ends as | Meaning |
|---|---|
| `finished` | The model called `finish` |
| `step_cap`, `token_budget` | A budget ran out |
| `context_exhausted` | The next step would not have fitted the context window |
| `no_action` | Too many replies without a tool call |
| `degenerate_loop` | The output was repeating itself |
| `wall_clock` | The safety net fired |
| `engine_failure` | The server failed twice; scored 0 and flagged, and may be re-run |

Whatever the ending, the files the model left behind are checked.

## Integrity

- **Hidden checks.** Each test's `hidden/` folder (checks and a reference solution) and `rubric.md`
  (the answer key) never enter a prompt or the model's container. A canary string sits in all of
  them; the runner aborts if it ever appears in a request.
- **Protected files.** If a model edits or deletes the repository's own tests, the originals are
  restored before checking and the change is reported.
- **Checks are tested.** `bench.py selftest` proves, with no model involved, that every check gives
  full marks to the reference solution and the expected minimum to an untouched fixture or a
  plausible wrong answer. Expected answers are computed independently of the reference solution
  wherever possible.
- **Fingerprints.** A run records a fingerprint of everything the model saw. If a test's prompt,
  files, or limits change, old runs stop counting and must be repeated. If only the grading changes,
  the check is re-applied to the saved output. If the rubric changes, old verdicts stop counting.

## Scoring

Each test is worth 10 points: scripted checks plus criteria judged by Claude (see `EVALUATION.md`).
About 70% of all points are scripted.

- A **category score** is the mean of its tests, as a percentage.
- The **Core score** is 45% agentic coding, 30% single-shot engineering, 15% long-context, 10% general.
- **Vision** is a separate column, so Core means the same for a model with and without image input.
- A test the model cannot take (no image input) is `n/a`, not zero.

Speed, time, and tool-call validity are reported next to the scores and never mixed into them.

## Limitations

- **Small and noisy.** Fifteen tests, one run each by default. Treat gaps of a few points as ties.
- **One machine.** Speed figures describe this Mac. Quality should transfer; timing does not.
- **An LLM judges an LLM.** Criteria are small, have fixed levels, and need a verbatim quote, and
  answers are judged from anonymous packets, but the judge can still be wrong. With only one model
  waiting to be judged the packets are not really anonymous. The scripted share is the firmer part.
- **Written by Claude.** The fixtures, answer keys, and rubrics were authored by the same family of
  model that judges them. Reviewing the rubrics of the judged tests is worthwhile.
- **Answer keys stay private.** The hidden checks, reference solutions, rubrics, test definitions,
  and raw transcripts are not in the public repository, because published answers end up in
  training data and stop measuring anything. The prompts and fixtures are public, so a future
  model may have seen the tasks, though not the answers.

## Changing the suite

Before the suite is frozen (`"frozen": false`), tests may change freely. After the freeze, any
change to what a model sees means a new suite version, and results from different versions are not
compared. `base/tests/README.md` describes how a test is built.
