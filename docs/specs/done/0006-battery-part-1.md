# Spec 0006: Red-team battery, part 1: leakage and overfitting

- **Status**: done
- **Depends on**: 0002, 0005
- **Blocks**: 0007, 0008
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

The red team attacks a claimed backtest. Each attack re-runs the strategy with one switch flipped, or
computes one statistic, and returns `PASSED`, `FAILED` or `INCONCLUSIVE`. The verdict is aggregated from
the attacks by fixed rules. This spec adds the verdict contract, the aggregation, and the first six
attacks: look-ahead leakage, survivorship, costs, selection bias, placebo and statistical power.

## 2. User stories

- As the orchestrator, I want one call that runs the battery on a claimed backtest and returns a verdict
  with every attack's metrics, so that the result can be stored and explained.
- As a reviewer, I want every threshold written down before the evaluation, so that the battery cannot be
  tuned on the cases it is judged on.

## 3. Applicable rules

- `RULE-TRIALS-01`: A4 deflates with every trial of the family.
- `RULE-SANITY-01`: an annualised Sharpe ratio above 2 sets the `suspicious` flag.
- `RULE-LLM-01`: the battery is deterministic; no LLM takes part.

## 4. Contracts and data model

- `AttackResult`: `attack_id`, `name`, `severity` (`fatal`, `serious`, `evidence`), `outcome`, `metrics`,
  `message`.
- `RedTeamReport`: `verdict`, `attacks`, `claimed_sharpe`, `suspicious`.
- Verdict rules, in order: a failed fatal attack gives `BROKEN`; else a failed serious attack gives
  `WOUNDED`; else an inconclusive evidence check gives `NOT_PROVABLE`; else `SURVIVES`.
- Attacks that test whether an edge survives a change are `INCONCLUSIVE` when the claimed Sharpe ratio is
  not positive: there is no edge to attack.

| ID | Attack | Severity | Fails when (calibrated on calibration seeds 1000-1004) |
|---|---|---|---|
| A1 | Look-ahead: trade one day later | fatal | Sharpe after the delay < 0.5 x claimed |
| A2 | Survivorship: point-in-time universe | fatal | claimed - point-in-time Sharpe > max(0.3, 0.5 x claimed) |
| A3 | Costs: volatility-dependent per-name costs | serious | net Sharpe <= 0 or < 0.3 x claimed |
| A4 | Selection bias: deflated Sharpe and PBO | serious | significant alone but deflated Sharpe < `min_deflated_sharpe`, or PBO > `max_overfitting_probability` |
| A5 | Placebo: signal shuffled across names | serious | placebo p-value > `max_p_value` |
| A10 | Power: probabilistic Sharpe ratio | evidence | inconclusive when PSR < 0.95; reports MinTRL and the minimum detectable Sharpe |

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| Python | `qmas.red_team.AttackContext` | Market, claimed strategy and result, trials, thresholds, seed. |
| Python | `qmas.red_team.run_battery(context, attacks)` | Run attacks and aggregate the verdict. |
| Python | `qmas.red_team.PART_ONE` | The attacks of this spec. |

The engine gains an optional `signal` argument (a precomputed matrix) used by the placebo.

## 6. Acceptance criteria

- [x] Verdict aggregation follows the rules above (tested with synthetic attack results).
- [x] Each attack fails on the planted defect it targets and passes on a clean planted signal (IC 0.08).
- [x] Every threshold lives in one `BatteryThresholds` object with the values of the table.
- [x] The battery is deterministic for a given seed.
- [x] `uv run poe check` passes.

## 7. Required tests

One test per attack (defect case fails, clean case passes, non-positive claim is inconclusive), the
aggregation rules, the `suspicious` flag, and determinism.

## 8. Out of scope

- A6, A7, A8, A9 and A13: spec 0007. A0, A11, A12, A14-A19: spec 0013.
- The E1 case library and its report: spec 0008.

## 9. Notes for the implementer

- The market gains `distress_decline` (a slide before delisting), needed for P2 to produce a convincing
  survivor-biased claim.
- A single-day jump or bad price cannot raise an annualised Sharpe ratio by more than about
  `sqrt(252 / T)`; attacks on those defects (A9, A13) must use PnL shares and source differences, not
  significance.

## Post-implementation notes

- Calibration (seeds 1000-1004, judgement seeds untouched): P1 BROKEN by A1 in 5/5; P2 BROKEN by A2 in
  4/5 (the fifth claim had a non-positive Sharpe after costs, so there was nothing to attack); P3 BROKEN
  by A1 and A3 in 5/5; P4 WOUNDED by A4 in 5/5; planted IC 0.04 and 0.08 SURVIVES in 10/10; IC 0 never
  survives.
- A1 also flags real edges that decay within a day (a one-day reversal): a one-day delay cannot tell them
  from look-ahead. Known limitation, documented.
- The engine was vectorised (identical results; a daily-rebalanced backtest takes about 80 ms) so that
  200 placebos per case are affordable.
