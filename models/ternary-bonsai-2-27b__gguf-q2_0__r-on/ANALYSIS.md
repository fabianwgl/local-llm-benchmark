# Analysis: Ternary Bonsai 2 27B (GGUF Q2_0, reasoning on)

Core 40.5. Suite v0.9.0, one run per test, judged 2026-11-22. Scores are in `SCORECARD.md`.

## Verdict

Capable when it gets to an answer, but it often does not: it spends its whole output budget
thinking. Four single-shot tests and two agentic tests ended with little or nothing delivered for
that reason. Worth using for review, short memos and images; not for long tasks.

## Strengths

- **Code review.** S1 9.0: all eight planted defects found, located and explained, with correct
  fixes.
- **Short structured answers.** G2 9.5 with no false claim, L2 8.5, S4 8.0.
- **Vision.** V1 9.5, V2 10.
- **Two agentic tasks done well.** A1 9.0 (every hidden test passed) and A5 7.1, although neither
  run reached `finish`.

## Failure patterns

- **Reasoning uses up the answer.** S2 and S3 hit the 16,384-token limit with an empty answer
  after 55,000 to 64,000 characters of reasoning (0.0 each). G1 was cut off part-way through its
  answer (3.5). L1 was still reasoning at the 30-minute wall clock (0.0).
- **Thinks past the step limit in agentic runs.** Every agentic run had three to five replies cut
  off at the 8,192-token step limit before any tool call. A2 and A4 ended as `no_action`: in A4
  it ran four shell commands in total and changed nothing.
- **Loops.** A3 ended as `degenerate_loop` with the crate still not compiling.
- **Severity ranking.** In S1 it rated five of the eight defects too low.

## Agentic behaviour

Tool calls were 100% valid, but no agentic run ended with `finish`, so every summary criterion
scored 0. A1 and A5 ran out of the 48,000-token budget with working code in place. A median of 50
minutes per agentic test. In A1 it added to a protected test file (additions only; restored before
checking).

## Speed

13 tokens/s and 0.18 s to the first token. The full suite took 447 minutes. Usable for short
single questions only.

## Caveats

- One run per test. The llama.cpp engine honours the seed, so these runs can be replayed.
- A 2-bit quantisation. A run with reasoning off (`--reasoning none`) would be a separate row and
  would show how much of the loss is the reasoning habit and not the model's ability; it has not
  been run.
- The judge had seen each configuration's scripted scores before judging this batch, and packets
  show scripted scores, so the blinding was weaker than the protocol intends.
