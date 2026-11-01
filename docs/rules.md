# Governance rules

These rules define how a trading hypothesis ("thesis") is tested. They exist because most backtests are wrong
in the same few ways: leakage, survivorship, ignored costs and, above all, trying many ideas and reporting
the best one. Each rule has a stable ID; code and tests cite it (`# Rule: RULE-PREREG-01`) so that a reader
can trace every guard back to its reason.

| ID | Rule | Why |
|---|---|---|
| `RULE-PREREG-01` | A thesis is registered in full, and its hash is written to the ledger, **before** the first backtest. Any later change is a new version. | Without pre-registration, the hypothesis drifts towards whatever the data showed. |
| `RULE-TRIALS-01` | Every backtest is a trial. The deflated Sharpe ratio uses the total number of trials of the thesis family, not only the last one. | Selecting the best of N trials inflates the Sharpe ratio; deflation corrects for it. |
| `RULE-ROUNDS-01` | At most two correction rounds per thesis, and only on the defects the red team reported. Each round is a new version and a new trial. | Unlimited fixing is curve fitting with extra steps. |
| `RULE-HOLDOUT-01` | The holdout window is the most recent window no test of the family has touched. It is opened once; if the thesis fails there, it is retired. | A holdout that is looked at twice is no longer a holdout. |
| `RULE-AUDIT-01` | Every number in a report comes from a stored result. A report whose figures cannot be traced is rejected. | Language models can produce plausible but invented figures. |
| `RULE-SANITY-01` | An annualised Sharpe ratio above 2 for a diversified long-only basket rebalanced monthly is flagged `SUSPICIOUS` and reviewed by a person before anything else. | Implausibly good results are far more often bugs than discoveries. |
| `RULE-FDR-01` | Across all theses tested in a year, the first one promoted to paper trading also needs a Benjamini-Hochberg adjusted p-value at 10 % over all of them. | Per-family deflation does not cover the search across families. |
| `RULE-LLM-01` | Language models may propose attacks, explanations and reports. They may add attacks or lower confidence, never raise it, and they never make the decision. Decisions come from deterministic code and a person. | Keeps every verdict reproducible and auditable. |
| `RULE-BUDGET-01` | Every LLM call goes through a client with a per-run and per-month spending cap. When the cap is reached, the run continues in simulated mode or stops; it never overspends. | Agent loops can spend money fast. |
| `RULE-HUMAN-01` | Promotion of a thesis (to paper trading or beyond) requires an explicit human approval, recorded in the ledger. | The system advises; a person decides. |
| `RULE-DATA-01` | Licensed or private data is never committed or redistributed. Users fetch their own data with their own keys. | Data licences usually forbid redistribution. |

## Verdicts

The red team returns one of four verdicts for a thesis:

| Verdict | Meaning |
|---|---|
| `BROKEN` | A fatal attack succeeded (for example, leakage or survivorship). The result is not real. |
| `WOUNDED` | No fatal attack succeeded, but a serious one did (for example, the edge disappears after costs). |
| `SURVIVES` | Every attack ran and none succeeded. This is not proof of an edge, only absence of known defects. |
| `NOT_PROVABLE` | Not enough data or statistical power to decide either way. |
