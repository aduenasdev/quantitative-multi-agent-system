# Spec 0001: Set up the repository foundation

- **Status**: done
- **Depends on**: none
- **Blocks**: every other spec
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

The project starts from an empty public repository. Before any domain code, it needs the tooling and the
rules that every later spec relies on: packaging, linting, type checking, tests, typed configuration, a
repository check that keeps the repository English-only and free of private data, the spec convention, the
first architecture decisions and a local Docker environment that runs the same checks.

## 2. User stories

- As a contributor, I want one command (`uv run poe check`) that runs every check, so that I know a change
  is ready to merge.
- As a reader of the public repository, I want clear rules and decisions, so that I understand how and why
  the project is built.
- As a user without Python set up, I want to run the checks in Docker, so that I do not depend on my machine.

## 3. Applicable rules

- `RULE-DATA-01`: `.gitignore` excludes data, databases and `.env`; the repository check rejects them.

## 4. Contracts and data model

- `qmas.config.Settings` (pydantic-settings, prefix `QMAS_`): `data_dir: Path`, `log_level`, `seed: int`.
  Loaded from the environment and from `.env` at the repository root when running from a source checkout.
- `[tool.check-repo]` table in `pyproject.toml`: `allowed_words`, `max_file_bytes`, `forbidden_patterns`.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| CLI | `qmas --version` | Prints the package version. |
| CLI | `qmas config show` | Prints the effective settings as JSON. |
| Task | `uv run poe check` | Lint, format check, type check, tests with coverage, repository check. |
| Task | `uv run poe secrets` | Runs gitleaks over the working tree and the history (needs gitleaks installed). |
| Script | `scripts/check_repo.py` | English-only check, private-string denylist, forbidden files. |
| Docker | `docker compose run --rm dev poe check` | Same checks inside the `dev` image. |

## 6. Acceptance criteria

- [x] `pyproject.toml` (PEP 621, hatchling, `src` layout) with pinned dependencies and `uv.lock`.
- [x] ruff (line length 100), `mypy --strict` and pytest (coverage of `src/qmas` at 85 % or more,
      network disabled) configured; `uv run poe check` passes.
- [x] `Settings` loads defaults, environment variables and `.env`; `.env.example` lists every variable.
- [x] Standard `logging` configured once through `qmas.logging_setup.configure_logging`.
- [x] `scripts/check_repo.py` fails on Spanish text, on denylisted strings (file given by
      `QMAS_DENYLIST_FILE`, kept outside the repository) and on forbidden or oversized files.
- [x] `AGENTS.md`, `README.md` (skeleton), `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- [x] `docs/rules.md`, the spec convention, template and index, and ADRs 0001-0004.
- [x] `Dockerfile` (`dev` target), `compose.yml` and `.dockerignore`; the checks pass in the container.
- [x] `.pre-commit-config.yaml` runs the same checks before each commit.

## 7. Required tests

- `test_settings_defaults`: defaults are applied when nothing is set.
- `test_settings_env_override`: `QMAS_*` environment variables override defaults.
- `test_settings_rejects_invalid_level`: an unknown log level fails validation.
- `test_cli_version` and `test_cli_config_show`: CLI output.
- `test_configure_logging_is_idempotent`: calling it twice does not duplicate handlers.
- `test_check_repo_*`: Spanish text, allowed words, denylist, forbidden files and size limit.

## 8. Out of scope

- Domain code (statistics, ledger, market, agents): specs 0002-0010.
- The `runtime` Docker image and `compose.prod.yml`: spec 0011.
- LLM settings: spec 0009.

## 9. Notes for the implementer

- Docker runs inside WSL on the author's machine; the `dev` service bind-mounts the repository, so the virtual
  environment lives in `/opt/venv` (outside the mount).
- The denylist must never be committed: it contains exactly the strings that must not be public.

## 10. Post-implementation verification

- `uv run poe check` passes on Windows and in `docker compose run --rm dev poe check`.
- `git ls-files` shows no data, no `.env`, no file over 1 MB.

## Post-implementation notes

- poe does not load `.env`: `scripts/check_repo.py` reads `QMAS_DENYLIST_FILE` from the environment or from
  `.env` itself, and the `dev` container sets it empty because the host path does not exist there.
- Docker check run on 2026-11-01: 23 tests passed in `qmas:dev` (Python 3.13, Linux).
