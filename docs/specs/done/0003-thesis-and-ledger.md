# Spec 0003: Add the thesis contract and the hash-chained ledger

- **Status**: done
- **Depends on**: 0001
- **Blocks**: 0010
- **Size**: S
- **Last updated**: 2026-11-01

## 1. Context and goal

A thesis must be written down completely before any data is looked at, and every later trial, verdict and
decision must be recorded in a log that cannot be edited silently. This spec defines the thesis contract
(a YAML file validated by Pydantic) and an append-only JSON Lines ledger in which every entry carries the
hash of the previous one, so that any edit, deletion or reordering is detected.

## 2. User stories

- As a researcher, I want to write a thesis in YAML and get its content hash, so that I can pre-register it.
- As a reviewer, I want `qmas ledger verify` to prove that the ledger was not altered.
- As the orchestrator, I want to refuse to backtest a thesis that is not registered.

## 3. Applicable rules

- `RULE-PREREG-01`: `Ledger.require_registered` raises unless the thesis hash is in the ledger.
- `RULE-TRIALS-01`: `Ledger.count_trials(family)` counts every trial recorded for a family.
- `RULE-HUMAN-01`: decisions are ledger entries of kind `decision`.

## 4. Contracts and data model

- `qmas.contracts.thesis.Thesis` (frozen): `thesis_id` (slug), `version`, `family`, `title`, `hypothesis`,
  `data` (`source`, `seed`, `parameters`), `signal` (`name`, `parameters`), `horizon_days`,
  `rebalance_every_days`, `design_window`, `holdout_window`, `cost_bps`, `thresholds`.
  `content_hash()` is the SHA-256 of its canonical JSON (sorted keys, no whitespace).
- Ledger line: `{"sequence", "timestamp", "kind", "payload", "previous_hash", "hash"}`; `hash` is the SHA-256
  of the canonical JSON of every other field; the first `previous_hash` is 64 zeros.
- Entry kinds: `thesis_registered`, `trial`, `verdict`, `decision`.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| Python | `qmas.contracts.thesis.load_thesis(path)` | Parse and validate a YAML thesis. |
| Python | `qmas.ledger.Ledger` | `append`, `entries`, `verify`, `register_thesis`, `require_registered`, `count_trials`. |
| CLI | `qmas thesis validate FILE` | Validate a thesis and print its hash. |
| CLI | `qmas ledger verify` | Verify the chain; exit code 1 on tampering. |

## 6. Acceptance criteria

- [x] Invalid theses (bad slug, holdout before design, unknown field) are rejected with a clear message.
- [x] The content hash ignores key order and formatting but changes with any value.
- [x] Editing, deleting, inserting or reordering a ledger line makes `verify` fail at that line.
- [x] Registering the same thesis twice is idempotent; a backtest of an unregistered thesis is refused.
- [x] `uv run poe check` passes.

## 7. Required tests

- `test_thesis_*`: validation errors, YAML round trip, hash stability.
- `test_ledger_*`: append and read back, each tampering case, empty ledger, idempotent registration,
  `require_registered`, `count_trials`.
- `test_cli_thesis_validate`, `test_cli_ledger_verify`.

## 8. Out of scope

- Signal registry and market data behind `signal.name` and `data.source`: specs 0004 and 0005.
- Concurrent writers: one process writes the ledger.

## 9. Notes for the implementer

- A hash chain detects tampering by anyone who cannot rewrite the whole file; it is not a signature. A
  published copy of the last hash (for example in a commit) anchors it.

## Post-implementation notes

- Registering a thesis key with different content is refused: the author must bump the version.
- `qmas.canonical` holds the canonical JSON and hashing shared by the thesis and the ledger.
