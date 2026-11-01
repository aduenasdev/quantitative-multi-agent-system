# Contributing

Read [AGENTS.md](AGENTS.md) first: it holds the coding, testing, configuration and git rules.

## Set up

```bash
uv sync                      # creates .venv with pinned dependencies from uv.lock
cp .env.example .env         # optional
uv run pre-commit install    # runs the checks before each commit
```

## Checks

| Command | What it runs |
|---|---|
| `uv run poe check` | ruff lint, ruff format check, mypy strict, pytest with coverage, repository check |
| `uv run poe format` | Formats the code |
| `uv run poe secrets` | gitleaks over the history and the working tree ([install gitleaks](https://github.com/gitleaks/gitleaks)) |
| `docker compose run --rm dev poe check` | The same checks in Docker |

The repository check (`scripts/check_repo.py`) keeps the repository English-only and rejects data files,
`.env` files and files over 1 MB. Maintainers also point `QMAS_DENYLIST_FILE` at a private list of strings
that must never be published; the list lives outside the repository.

## Workflow

1. Pick or write a spec in `docs/specs/` ([convention](docs/specs/README.md)).
2. Branch: `git switch -c feat/spec-NNNN-short-title`.
3. Implement with tests; tick the acceptance criteria.
4. `uv run poe check`.
5. Commit with Conventional Commits naming the spec, e.g. `feat(0004): add synthetic market`.
6. Merge into `main` with `--no-ff` and delete the branch.
