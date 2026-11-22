# Analysis: Bonsai 27B (MLX 2bit, reasoning on)

Core 47.5. Suite v0.9.0, one run per test, judged 2026-11-22. Scores are in `SCORECARD.md`.

## Verdict

An 8.5 GB model that reads and explains well: it had the best long-context score in this batch and
full marks on root-cause analysis, meeting notes and a screenshot. It is not a coding agent: four
of five repository tasks scored 2.3 or less, and it could not write the SQL.

## Strengths

- **Diagnosis from text.** S2 10.0, with the full mechanism, the timing, the fix and a test. L1
  8.0, one of only two configurations to answer the long log at all.
- **General and vision.** G1 10, V1 10, V2 9.8.
- **One clean bug fix.** A1 9.0: every hidden test passed in 22 steps.
- **Size.** At 8.5 GB it is one of the two smallest configurations tested.

## Failure patterns

- **Loops instead of acting.** A3 and A5 ended as `degenerate_loop`: after reading the code, the
  reasoning started repeating itself. In A5 it made 30 reads and no edit. In A3 it made four whole-file
  rewrites across three files and the crate still did not build.
- **Wrong SQL.** S3 0.0: it answered, but none of the four queries was right on either database.
- **Summaries that claim more than the diff.** In A1 the summary described a fix that the diff
  does not contain, which cost the judged point. In A4 it called `finish` with the job still
  producing no correct report, and its summary gave a cause that its own diff contradicts (2.0).
- **False technical claims.** In G2 it recommended an option on the strength of a statement about
  the database setup that is not true (6.0).
- **Misses in review.** S1 5.0: four of eight planted defects found.

## Agentic behaviour

Tool calls were 99% valid, so the mechanics work. The problem is direction: A2 spent the whole
48,000-token budget and delivered a fraction of the feature (2.3), and A4 used all 40 steps. Two
runs ended with `finish`. A median of 28 minutes per agentic test. In A4 it edited an existing
migration; the harness restored it before checking.

## Speed

16 tokens/s and 1.0 s to the first token. Acceptable for single questions (2 to 23 minutes each
here, the longest on the 30,000-token inputs), slow for agentic work.

## Caveats

- One run per test, on the MLX engine, which ignores the seed.
- A 2-bit quantisation of a 27B model. The same model at a higher bit width would be a different
  row and has not been run.
- The judge had seen each configuration's scripted scores before judging this batch, and packets
  show scripted scores, so the blinding was weaker than the protocol intends.
