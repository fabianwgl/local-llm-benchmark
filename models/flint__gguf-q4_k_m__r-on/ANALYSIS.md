# Analysis: Flint (GGUF Q4_K_M, reasoning on)

Core 61.3. Suite v0.9.0, one run per test, judged 2026-11-22. Scores are in `SCORECARD.md`.

## Verdict

The strongest single-shot engineer tested: when the task is one prompt and one answer, it is the
most accurate configuration here. As an agent it works carefully but too slowly for the step
budget, so three of five repository tasks ran out of steps with nothing usable. It has no image
input.

## Strengths

- **Single-shot engineering, 93.8.** Full marks on S2 (root cause), S3 (all four SQL queries on
  both databases, the only configuration to do so) and S4 (all eleven tool-calling cases, also the
  only one). S1 7.5.
- **Clean agentic work when it fits the budget.** A1 10.0, one of two perfect agentic scores in
  this batch, with an accurate summary and a focused diff. A5 9.0: all golden cases preserved, the
  differences modelled as named options.
- **General.** G1 10, G2 8.0.
- **Codebase questions.** L2 8.0.

## Failure patterns

- **Runs out of steps mid-edit.** A2, A3 and A4 all ended at the 40-step cap. The transcripts show
  the same shape each time: twenty or more file reads, then many small `edit_file` calls on one
  file, and the cap arriving before the work compiles or runs. A3 and A4 scored 0; A2 scored 1.2.
- **Never calls `finish` under pressure.** Four of five agentic runs ended without a summary,
  including A5, where the code was complete and correct but the token budget ran out first.
- **Over-thinks a long input.** L1 ended at the 30-minute wall clock while still reasoning, with
  no answer (0.0). This happened once.
- **Severity ranking.** In S1 it found seven of the eight planted defects but rated several of
  them too low.

## Agentic behaviour

Tool calls were 99% valid. It reads thoroughly and edits in small increments, which is safe but
expensive: a median of 41 minutes per agentic test, and only A1 ended with `finish`. In A1 it
added to the repository's protected test files (additions only; they were restored before
checking).

## Speed

37.4 tokens/s in the speed probe, dropping to 16 to 27 tokens/s inside long agentic runs. Usable
interactively for single questions. Whole-repository tasks took 25 to 58 minutes each.

## Caveats

- One run per test. The llama.cpp engine honours the seed, so these runs can be replayed.
- No vision: V1 and V2 are n/a and do not affect Core.
- The 30-minute wall clock is meant as a safety net, yet it ended L1 before any answer. See the
  README's note on time limits.
- The judge had seen each configuration's scripted scores before judging this batch, and packets
  show scripted scores, so the blinding was weaker than the protocol intends.
