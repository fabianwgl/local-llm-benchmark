# Local LLM Benchmark

**Which local model can actually do a software engineer's work on a 36 GB MacBook Pro?**

Each model is loaded in [LM Studio](https://lmstudio.ai), given the same 15 tasks under the same
conditions, and scored out of 100. The tasks are real work: fixing bugs in a repository, writing
SQL, reviewing a pull request, finding the cause of an incident in a long log. Scripts check about
70% of the points; Claude judges the rest from anonymous answers.

## Results

<!-- results:start -->
| # | Model | Build | Size | Reasoning | Core | Agentic | Single-shot | Long-context | General | Vision | Tokens/s | Full suite |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [Qwen3.6 35B A3B](models/qwen3.6-35b-a3b__mlx-4bit__r-on/SCORECARD.md) | MLX 4bit | 20.4 GB | on | **64.2** | 56.2 | 76.2 | 45 | 92.5 | 94.2 | 55.6 | 84 min |
| 2 | [Flint](models/flint__gguf-q4_k_m__r-on/SCORECARD.md) | GGUF Q4_K_M | 24.2 GB | on | **61.3** | 40.3 | 93.8 | 40 | 90 | n/a | 37.4 | 283 min |
| 3 | [Qwen3.8 27B](models/qwen3.8-27b__mlx-4bit__r-xhigh/SCORECARD.md) | MLX 4bit | 16.1 GB | xhigh | **49.5** | 54.5 | 42.5 | 50 | 47.5 | 100 | 8.8 | 625 min |
| 4 | [Bonsai 27B](models/bonsai-27b__mlx-2bit__r-on/SCORECARD.md) | MLX 2bit | 8.5 GB | on | **47.5** | 28.7 | 57.5 | 62.5 | 80 | 99.2 | 16 | 291 min |
| 5 | [Ternary Bonsai 2 27B](models/ternary-bonsai-2-27b__gguf-q2_0__r-on/SCORECARD.md) | GGUF Q2_0 | 8.6 GB | on | **40.5** | 33.1 | 42.5 | 42.5 | 65 | 97.5 | 13 | 447 min |

Points per test (each test is worth 10):

| Model | `A1` | `A2` | `A3` | `A4` | `A5` | `S1` | `S2` | `S3` | `S4` | `L1` | `L2` | `G1` | `G2` | `V1` | `V2` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [Qwen3.6 35B A3B](models/qwen3.6-35b-a3b__mlx-4bit__r-on/SCORECARD.md) | 8.6 | 7.2 | 8.3 | 3 | 1 | 7.5 | 7 | 7.5 | 8.5 | 9 | 0 | 10 | 8.5 | 10 | 8.8 |
| [Flint](models/flint__gguf-q4_k_m__r-on/SCORECARD.md) | 10 | 1.2 | 0 | 0 | 9 | 7.5 | 10 | 10 | 10 | 0 | 8 | 10 | 8 | n/a | n/a |
| [Qwen3.8 27B](models/qwen3.8-27b__mlx-4bit__r-xhigh/SCORECARD.md) | 8.6 | 10 | 0 | 0.5 | 8.1 | 9 | 0 | 0 | 8 | 0 | 10 | 0 | 9.5 | 10 | 10 |
| [Bonsai 27B](models/bonsai-27b__mlx-2bit__r-on/SCORECARD.md) | 9 | 2.3 | 0 | 2 | 1 | 5 | 10 | 0 | 8 | 8 | 4.5 | 10 | 6 | 10 | 9.8 |
| [Ternary Bonsai 2 27B](models/ternary-bonsai-2-27b__gguf-q2_0__r-on/SCORECARD.md) | 9 | 0.5 | 0 | 0 | 7 | 9 | 0 | 0 | 8 | 0 | 8.5 | 3.5 | 9.5 | 9.5 | 10 |

- Updated 2026-11-22. Suite v0.9.0 (not frozen yet). Measured on Apple M3 Pro with 36 GB RAM, LM Studio 0.4.28+2. One run per test unless a scorecard says otherwise, so gaps of a few points are ties.
<!-- results:end -->

**Reading the table**

- **Core** is the headline score, 0 to 100. It weights the four categories next to it: 45% agentic
  coding, 30% single-shot engineering, 15% long-context, 10% general.
- **Vision** is reported on its own, so that Core means the same for models with and without image
  input.
- **Tokens/s** is generation speed on this machine. **Full suite** is how long all 15 tests took.
  Neither affects a score.
- A row is one **configuration**: a model at one quantisation and one reasoning level. The same
  model at another quantisation is a different row.
- Click a model name for its scorecard: every test, how each run ended, and the points for each
  check and judged criterion. `ANALYSIS.md` in the same folder says what went well and what did not. [LEADERBOARD.md](LEADERBOARD.md) has the full comparison, including tool-call
  reliability.

## What is tested

| Category | Weight in Core | Tests | What the model has to do |
|---|---|---|---|
| Agentic coding | 45% | `A1` to `A5` | Work in a repository inside a sandbox with five tools (read, write, edit, run a command, finish): fix rounding bugs in TypeScript, build a feature in Python from a spec, repair a Rust crate, fix a nightly bash and SQL job, refactor duplicated code. Hidden tests run afterwards |
| Single-shot engineering | 30% | `S1` to `S4` | One prompt, one answer: review a pull request with planted defects, find a root cause behind a misleading stack trace, write four hard SQL queries, call tools correctly under operating rules |
| Long-context | 15% | `L1`, `L2` | Find the cause of an incident in about 30,000 tokens of merged logs; answer questions that need tracing through a 46-file codebase |
| General | 10% | `G1`, `G2` | Turn a messy meeting transcript into decisions and action items; write a constrained technical decision memo |
| Vision | separate | `V1`, `V2` | Diagnose a failure from a terminal screenshot; read an architecture diagram |

The full catalog is in [base/docs/TESTS.md](base/docs/TESTS.md). The prompts and the files each
model receives are in [base/tests/](base/tests/).

## How it works

1. **Same conditions for every model.** One model in memory, an 80,000-token context, one fixed
   sampler, one fixed system prompt, and the same output budget (thinking included). Running out
   of budget is a recorded outcome, scored on what was delivered, and never retried with more.
2. **A minimal agent harness.** Agentic tests run in a Docker container with no network. The
   harness is identical for every model and never repairs a malformed tool call, so the result
   reflects the model and not a product's scaffolding.
3. **Scripted checks first.** Hidden tests, exact answers, and queries run against a hidden
   database decide about 70% of the points.
4. **Blind judging for the rest.** Claude judges the remaining criteria (for example "does the
   summary name the real cause?") from anonymous packets with model names removed. Every criterion
   has fixed levels, and every award must quote the answer word for word.
5. **Speed is reported, never scored.** A slow model that gets it right beats a fast model that
   does not.

Details: [METHODOLOGY.md](base/docs/METHODOLOGY.md) for what is measured and why,
[EVALUATION.md](base/docs/EVALUATION.md) for the judging protocol.

## How far to trust this

- **Small and noisy.** Fifteen tests and, by default, one run each. Gaps of a few points are ties.
- **One machine.** Speed describes an Apple M3 Pro with 36 GB of RAM. Quality should transfer to
  other machines; timing does not.
- **Slow configurations lose points to the clock.** The time limits (30 minutes for a single
  answer, 90 for an agentic task) are meant as a safety net, but a configuration that generates
  fewer than about 10 tokens/s can reach them before it has spent its token budget. Qwen3.8 at
  `xhigh` reasoning ended six tests that way, four of them with no answer.
- **An LLM judges an LLM.** The judged criteria are small and need verbatim evidence, but the
  judge can still be wrong. The scripted share is the firmer part.
- **Written by Claude.** The tasks, answer keys, and rubrics were written with Claude, the same
  model family that judges. That is a possible bias toward answers Claude would give.
- **Still changing.** The suite is at v0.9 and not frozen. When a test changes, old runs of it
  stop counting and are repeated, so scores from different suite versions are never mixed.

## What is in this repository

```
README.md          this page; the results block is generated
LEADERBOARD.md     generated comparison of every configuration
base/
  docs/            methodology, test catalog, judging protocol, how to run
  tests/<id>/      what each model is given: the prompt, the repository or input files
  runner/          the benchmark runner (Python standard library only) and the sandbox image
  suite.json       the fixed settings, budgets, and weights
models/<slug>/     one folder per configuration tested
  SCORECARD.md     generated: scores per test, check and criterion; speed; reliability
  ANALYSIS.md      written assessment: strengths, failure patterns, when to use it
  model.json       exactly what was loaded and on what hardware
  runs/            per test: how the run ended, timing, token and tool-call counts
```

**The answer keys are not here.** The hidden checks, reference solutions, rubrics, and test
definitions stay private, and so do the raw transcripts and the judge's written reasons, because
successful runs and the verdicts on them restate the solutions. A benchmark whose answers are public ends up in training data and stops
measuring anything. The cost is that a clone of this repository cannot score a model: the runner
is published so that you can read exactly how models are driven and graded, not as a ready-to-run
tool.

## Want a model tested?

Open an issue with the model's name and its LM Studio key. It has to fit in 36 GB of memory at an
80,000-token context, which in practice means files of up to about 24 GB. New models are added as
they come out, and each result is a new row above.

For how a model is run and judged, see [base/docs/RUNNING.md](base/docs/RUNNING.md).

## License

[MIT](LICENSE). Please do not use the contents of this repository to train models.
