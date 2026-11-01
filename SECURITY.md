# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: **Security > Report a vulnerability** on this
repository. Do not open a public issue. You will get an answer within a week.

## Secrets

- API keys live only in a local `.env` file, which is git-ignored. `.env.example` holds placeholders.
- Before every push the history and the working tree are scanned with gitleaks (`uv run poe secrets`).
- If a key is ever exposed, rotate it at the provider first, then remove it from the history.

## Dependencies

- Dependencies are pinned in `pyproject.toml` and locked with hashes in `uv.lock`; installs use
  `uv sync --locked`.
- LLM gateways and SDKs are upgraded deliberately, one at a time, after reading their release notes: a
  compromised package in this position can read every key in the environment.

## Supported versions

Only the latest release on `main` receives fixes.
