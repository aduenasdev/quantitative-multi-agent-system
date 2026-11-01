# Project rules

Rules for everyone who changes this repository, people and AI coding agents alike. They are mandatory.
Governance rules for testing a trading thesis are separate: [docs/rules.md](docs/rules.md).

## 1. English only

- Code, identifiers, comments, docstrings, log messages, CLI output, commit messages and documentation are
  written in English.
- `scripts/check_repo.py` enforces it. Proper names that need non-ASCII letters go in
  `[tool.check-repo].allowed_words` in `pyproject.toml`.

## 2. Coding standard

- Python 3.12+, **PEP 8** through **ruff** (`ruff check` and `ruff format`, line length 100), **PEP 257**
  docstrings for public modules, classes and functions.
- Type hints everywhere; `mypy --strict` passes on `src`, `tests` and `scripts`.
- Names: `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for
  constants. No abbreviations that a newcomer would not understand.
- Imports at the top of the file, grouped standard library, third party, local.
- Paths are built with `pathlib` from the settings or the repository root, never from the working directory.
- Diagnostics go through the standard `logging` module (`qmas.logging_setup`), not `print`. The CLI may print
  its results.
- No dead code: a module nobody imports is deleted.
- Statistical methods cite their source (paper or textbook) in the docstring.
- Code that enforces a governance rule cites it: `# Rule: RULE-PREREG-01`.
- Randomness always comes from an explicit `numpy.random.Generator` built from a seed; never the global state.

## 3. Tests

- `pytest` with real assertions. Tests never use the network (`pytest-socket` blocks it) or API keys.
- Coverage of `src/qmas` stays at 85 % or more.
- Statistical code is tested with analytical special cases, Monte Carlo properties or invariants, never with
  numbers copied from memory.

## 4. Configuration and secrets

- Every environment-specific value (keys, model names, paths, limits) lives in `.env`, loaded into the typed
  `qmas.config.Settings`. Nothing else reads `os.environ`.
- `.env.example` lists every variable with a comment: what it is, its default and where to get it.
- Without keys, the system runs in an explicit `simulated` mode and says so.
- `.env`, data, databases, logs and anything licensed are never committed (`RULE-DATA-01`).
- Nothing in the repository refers to private infrastructure, private projects or personal data.

## 5. Specs and decisions

- Every change starts from a spec in `docs/specs/` following [docs/specs/README.md](docs/specs/README.md).
- Architecture decisions are recorded as ADRs in `docs/decisions/` (MADR format). A decision that changes
  an ADR gets a new ADR that supersedes it.

## 6. Git

- One branch per spec (`feat/spec-NNNN-short-title`), merged into `main` with `--no-ff` once
  `uv run poe check` passes; the branch is then deleted.
- Conventional Commits naming the spec: `feat(0003): add hash-chained ledger`.
- Author: Alejandro Dueñas. No tool or co-author attribution lines in commits.
- Before any push: `uv run poe check`, `uv run poe secrets` and the repository check with the private denylist.

## 7. Definition of done

A spec is done when every acceptance criterion is ticked, `uv run poe check` passes locally and in Docker
(`docker compose run --rm dev poe check`), the spec is moved to `docs/specs/done/` and
[docs/specs/INDEX.md](docs/specs/INDEX.md) is updated.
