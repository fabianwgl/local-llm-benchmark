# Analysis: Qwen3.8 27B (MLX 4bit, reasoning xhigh)

Core 49.5. Suite v0.9.0, one run per test, judged 2026-11-22. Scores are in `SCORECARD.md`.

## Verdict

When it finishes, its answers are the best in this batch; at its shipped `xhigh` reasoning level it
is too slow on this machine to finish reliably. Six of fifteen tests ended at the wall clock, four
of them with no answer at all, so the Core score mostly measures speed here, not ability.

## Strengths

- **Quality of completed work.** A2 10.0, the only full implementation of the feature, in the
  right modules, with documentation and tests. L2 10.0, the only configuration to answer all
  eight codebase questions, with both traces correct. G2 9.5, S1 9.0 (all eight planted defects
  found and explained), V1 10, V2 10.
- **Preserving behaviour in a refactor.** A5 8.1 with the differences modelled as named options.
- **Tool calls.** 99% valid.

## Failure patterns

- **Still thinking when time runs out.** S2, S3, L1 and G1 ended at the 30-minute wall clock with
  an empty answer, each after 19,000 to 57,000 characters of reasoning. At about 8.5 tokens/s the
  16,384-token output budget takes 32 minutes to spend, so a long deliberation cannot fit.
- **Thinks past the step limit.** In A3 three replies hit the 8,192-token step limit while
  reasoning, with no tool call, and the run ended as `no_action` after reading the code (0.0).
- **Spends its steps on diagnosis.** In A4 it used 34 shell commands across 40 steps and reached
  the step cap with the job still failing (0.5).
- **Severity ranking.** In S1 it rated two of the eight defects too low.

## Agentic behaviour

Only A1 ended with `finish`. A2 and A5 produced correct or nearly correct code and were then cut
off by the 90-minute wall clock before a summary, which cost judged points in A5. A median of 85
minutes per agentic test. In A1 it added to the repository's protected test files (additions only;
restored before checking).

## Speed

8.8 tokens/s and 1.5 s to the first token. The full suite took 625 minutes. Too slow for
interactive use at this reasoning level.

## Caveats

- **This row is about `xhigh`.** The model also offers `low`, `medium` and `off`. A lower level
  would be a separate row and would very likely avoid the wall-clock endings; it has not been run.
- The wall clock is meant as a safety net so that speed is not scored as quality. For this
  configuration it ended six tests, four of them with no answer, so compare its Core with care.
- One run per test, on the MLX engine, which ignores the seed.
- The judge had seen each configuration's scripted scores before judging this batch, and packets
  show scripted scores, so the blinding was weaker than the protocol intends.
