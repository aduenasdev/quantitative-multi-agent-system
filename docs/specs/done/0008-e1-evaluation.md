# Spec 0008: Evaluate the battery on planted cases (E1)

- **Status**: done
- **Depends on**: 0006, 0007
- **Blocks**: 0011
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

A red team is only useful if its error rates are known. E1 runs the full battery on cases whose truth is
known: ten planted defects and five planted signal strengths, each on five seeds, and checks three
criteria written before the run. The result is published as it comes out.

## 2. User stories

- As a reader of the repository, I want a confusion matrix of planted cases against verdicts, so that I can
  judge the battery by its errors and not by its description.
- As a researcher, I want calibration seeds and judgement seeds kept apart, so that the thresholds were
  not tuned on the cases they are judged on.

## 3. Applicable rules

- `RULE-PREREG-01` (in spirit): criteria and thresholds are fixed in code before the judgement run.

## 4. Contracts and data model

- Case library (`qmas.evaluation.cases`): P1-P10 from the evaluation plan, each with its expected attack,
  and planted signals with rank IC 0, 0.01, 0.02, 0.04 and 0.08.
- Seeds: calibration 1000-1004 (thresholds were tuned here), judgement 2000-2004 (the verdict).
- `E1Report`: every case outcome, the confusion matrix, the minimum detectable Sharpe ratio, the expected
  Sharpe ratio of each planted level (from calibration seeds) and the three criteria:
  1. at least 95 % of defect claims caught (`BROKEN` or `WOUNDED`); a defect case whose claimed Sharpe is
     not positive is reported but left out, because nobody would bring it;
  2. at most 10 % of IC 0 cases `SURVIVES`;
  3. at least 80 % of planted signals above the minimum detectable Sharpe `SURVIVES`.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| CLI | `qmas evaluate e1 [--split calibration\|judgement] [--quick] [--workers N] [--output DIR]` | Run E1 and write `e1-<split>.json` and `.md`. |
| Python | `qmas.evaluation.run_e1(seeds, thresholds, workers, progress, templates)` | Programmatic run. |

## 6. Acceptance criteria

- [x] The case library holds P1-P10 and the five planted levels.
- [x] Parallel and serial runs give identical outcomes.
- [x] The report renders the criteria, the confusion matrix and every case.
- [x] The judgement run is executed once, after the thresholds are merged, and its report is published.
- [x] `uv run poe check` passes.

## 7. Required tests

Library contents, the selection case (best of its trials), one case end to end, the criteria with and
without positive claims, a subset run with rendering and JSON round trip, serial against parallel, the CLI.

## 8. Out of scope

- Known nulls, validated strategies and real bugs on real data (the other half of the evaluation plan):
  they need data that cannot be published.
- E2 (does the LLM add anything) and E3 (forward): later specs.

## Post-implementation notes

- Run 1 on judgement seeds 2000-2004 FAILED the third criterion: defects 46/46 caught, noise 0/5
  surviving, detectable signals 5/10 surviving (criterion 80 %). Published in docs/research/e1-run-1.md.
- Cause: A7 and A8 thresholds tuned on five calibration seeds per level. Amendment 1 (spec 0008a)
  recalibrates on a larger calibration set and repeats E1 on new judgement seeds.
- The full run takes about five minutes with seven worker processes.
