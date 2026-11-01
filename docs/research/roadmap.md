# Roadmap

v0.1.0 is the MVP: the desk, the battery and its evaluation on a synthetic market, fully offline. Each
next step is one spec ([index](../specs/INDEX.md)) and one release.

| Spec | Step | Why it matters |
|---|---|---|
| 0012 | LLM red team proposes extra attacks from closed templates, measured against the battery alone (E2) | Does the LLM find defects the battery misses, and at what cost per defect? It may only add attacks (`RULE-LLM-01`) |
| 0013 | Complete battery: cemetery of retired ideas, Fama-French factors on real data, event-day, delay-curve, tail, cost-per-name, decay, execution-price, independent-reimplementation and turnover attacks | The ten defects of E1 are a minimum, not the list of what goes wrong |
| 0014 | First real-data thesis on public crypto data | A full public replication, data included |
| 0015 | SEC insider and 13F data (free, official) | Re-test the insider-purchase lead of the [prior study](prior-study-catalysts.md) on new data |
| 0016 | Port of the catalyst event study, with Alpaca prices and SEC filings | Real data through the desk, compared with the hand-made study |
| 0017 | Knowledge base of retired theses | A thesis that resembles a known null must say what changed |
| 0018 | Technical analyst agent (deterministic detectors first) | A second specialist with its own measured error rate |

Later: correction rounds and the single holdout opening (`RULE-ROUNDS-01`, `RULE-HOLDOUT-01`), a paper
book for what survives, a forward evaluation (E3), and the global false-discovery rule across families
(`RULE-FDR-01`).
