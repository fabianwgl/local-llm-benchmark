# Evaluation: how Claude judges

Scripts decide about 70% of the points. Claude decides the rest, and writes the analysis. This
document is the protocol. Follow it the same way every time, so that a verdict written today and
one written months from now mean the same thing.

## Who does what

| Step | Done by | Output |
|---|---|---|
| Run the tests | the user, with `bench.py run` | `models/<slug>/runs/<test>/s<seed>/` |
| Scripted checks | `bench.py run` / `check` | `check.json` |
| Build blind packets | `bench.py packet` | `judging/<batch>/<test>/<id>.md` |
| Judge each packet | Claude, in the main session | `<id>.verdict.json` |
| Validate, add up, report | `bench.py score` | `verdict.json`, `SCORECARD.md`, `LEADERBOARD.md` |
| Write the analysis | Claude, after scores are final | `models/<slug>/ANALYSIS.md` |

Claude never adds up scores and never edits `SCORECARD.md` or `LEADERBOARD.md`. Claude does not
start model runs unless the user asks, and does not hand judging to subagents.

## Workflow

1. `python3 base/runner/bench.py status` and confirm the runs you expect are finished.
2. `python3 base/runner/bench.py packet`. This writes one folder per test under `judging/<batch>/`,
   each holding `RUBRIC.md`, `CRITERIA.json`, and one packet per run under a random id. Model names
   are scrubbed. When earlier verdicts exist, two already-judged packets per test are mixed in as
   anchors.
3. Judge the folders one test at a time, as described under "Judging a test folder" below.
4. `python3 base/runner/bench.py score --judge-model <your model id>`. It rejects any verdict that
   breaks the rules below and says why. Fix by re-judging that packet; never by editing numbers.
5. If `score` reports anchor drift of more than one point on a test, the rubric is being read
   differently than before. Re-judge that test's packets (`bench.py packet --tests <id> --rejudge`)
   so that all models are judged under one reading.
6. Write or update `ANALYSIS.md` for each model that was judged (see the end of this document).

### Judging a test folder

1. Read the folder's `RUBRIC.md` and `CRITERIA.json` before any packet.
2. Judge every packet in the folder in one sitting, in file-name order. The ids are random, so the
   order says nothing about which model wrote what.
3. Judge each packet against the rubric, not against the other packets.
4. Write `<id>.verdict.json` next to each packet before moving to the next one.
5. Finish the folder before starting another test.

**Staying blind.** Packets are anonymous: random ids, model names removed. Keep them that way.
While judging, do not open `judging/<batch>/map.json`, anything under `models/`, or the
transcripts. Look up which model wrote which answer only after `score` has stored the verdicts.

Blindness needs more than one candidate. If only one model has runs waiting, every packet is known
to be that model's. Prefer to judge once two or more models have runs waiting. If that is not
possible, judge anyway and say so in the verdict's `notes` ("single-model batch").

## Rules for a verdict

1. **Judge the criteria, nothing else.** Each criterion in `CRITERIA.json` has a fixed range and
   step, and `RUBRIC.md` says what each level means. Pick the level whose description fits. Do not
   invent levels, and do not reward or punish anything the rubric does not mention (style, length,
   politeness, formatting).
2. **Use the packet's evidence.** A packet contains the task, the scripted check results, the
   model's answer, and for agentic tests the diff. The scripted results are facts: if the checks
   say the tests failed, a summary claiming they pass is false.
3. **Quote.** Every award needs a `quote`: text copied character for character from the packet that
   shows why. For a criterion that rewards the absence of something (marked `"evidence": "absence"`
   in `CRITERIA.json`), full marks need no quote, and anything less needs a quote of the offending
   text. `score` checks that every quote really occurs in the packet.
4. **When in doubt, the lower level.** If you cannot point to the text that earns a level, it has
   not been earned.
5. **One sentence of reason** per criterion, saying what in the answer decided it.
6. **Do not guess the model.** If an answer names itself, ignore it.
7. **Consistency over generosity.** Two answers with the same content get the same level, however
   differently they are worded.

## Verdict format

One JSON file per packet, named `<id>.verdict.json`:

```json
{
  "packet": "a1b2c3",
  "criteria": {
    "root_cause_stated": {
      "points": 0.5,
      "quote": "Fixed rounding issues in money.ts",
      "reason": "Names where the change was made but not what was wrong, and covers one of the two fixes."
    },
    "focused_diff": {
      "points": 1,
      "quote": "+test(\"SUP-3312: tax is rounded once per invoice\"",
      "reason": "The diff touches only the two defective functions and adds a regression test."
    }
  },
  "notes": "Optional: anything a reader of the scorecard should know."
}
```

Every criterion id from `CRITERIA.json` must appear exactly once. `points` must lie on the
criterion's step grid between its minimum (0 unless stated) and its maximum.

## Writing ANALYSIS.md

After `score` has accepted all verdicts for a model, write `models/<slug>/ANALYSIS.md`. This is the
one place for judgement in prose. It does not change any score. Base it on the transcripts
(`transcript.jsonl`), the answers, and the scorecard, and keep it to about a page:

- **Verdict in two sentences**: what this model is good for on this machine, and what not.
- **Strengths**, each with the test that shows it.
- **Failure patterns**: what kind of mistake it makes, with one concrete example each (for example
  "stops after describing a plan", "edits tests to make them pass", "ignores the last constraint").
- **Agentic behaviour**: how it used its steps and budget, tool-call reliability, how runs ended.
- **Speed**: whether it is fast enough to work with interactively.
- **Caveats**: single run, anything odd about the runs.

State only what the artifacts show. If a pattern appears once, say it appeared once.

## Pitfalls

- A long, confident answer is not a correct one. Check each claim against the rubric's key.
- Do not give credit for a correct statement that sits next to a wrong one when the criterion asks
  for "nothing false".
- Partial levels exist so that they are used: an answer that is half right gets the half level.
- If a rubric turns out to be ambiguous, do not resolve it silently. Judge with the stricter
  reading, report the ambiguity, and fix the rubric before the next batch (that changes the rubric's
  fingerprint, so earlier verdicts for that test are redone).
