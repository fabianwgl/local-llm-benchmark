# Analysis: Qwen3.6 35B A3B (MLX 4bit, reasoning on)

Core 64.2. Suite v0.9.0, one run per test, judged 2026-11-22. Scores are in `SCORECARD.md`.

## Verdict

The best all-round configuration tested so far, and by a wide margin the fastest: it finished the
whole suite in 84 minutes at about 56 tokens/s. Use it as the default for interactive work on this
machine, but check its work on larger refactors and on questions over a big context, where two
runs produced nothing at all.

## Strengths

- **Agentic coding that finishes.** The only configuration that got the broken Rust crate building
  (A3, 8.3), in 21 steps and under five minutes, with the idiomatic fix and an accurate summary.
  A1 (8.6) and A2 (7.2) were also solid.
- **General and vision work.** G1 10, G2 8.5, V1 10, V2 8.8.
- **Reading a long log.** L1 9.0: every scripted field right, including the exact count that the
  other configuration that answered got wrong.
- **Tool calls.** 100% valid across the agentic tests.

## Failure patterns

- **Thinks past the step limit and never acts.** In A5 it read the code, then five replies hit the
  8,192-token step limit while still reasoning, with no tool call. The run ended as `no_action`
  with no file changed (1.0).
- **Loops on a large input.** L2 ended as `degenerate_loop` inside the reasoning and gave no
  answer (0.0). This happened once.
- **Stops at the first plausible explanation.** In S2 it found the defect and the fix but
  explained the timing of the failures wrongly (7.0). In A4 it fixed part of the job and its
  summary claimed a result that the checks contradict (3.1).
- **Edits files it should leave alone.** In A4 it changed an existing migration; the harness
  restored it before checking.

## Agentic behaviour

Three of five runs ended with `finish`; A2 hit the 40-step cap with most of the feature in place
but no summary; A5 ended without action. It explores first and batches several reads into one
step, so it uses steps efficiently: a median of 9.4 minutes per agentic test.

## Speed

55.6 tokens/s in the speed probe and 0.27 s to the first token. Fast enough to work with
interactively, and the only configuration here for which that is clearly true.

## Caveats

- One run per test, on the MLX engine, which ignores the seed. The two zero-point runs (A5, L2)
  may not repeat; a second seed would show how often they do.
- Swap grew during A2, so that run's timing is unreliable.
- The judge had seen each configuration's scripted scores before judging this batch, and packets
  show scripted scores, so the blinding was weaker than the protocol intends.
