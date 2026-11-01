# Spec 0011: Deliver v0.1.0

- **Status**: in-progress
- **Depends on**: 0008, 0008a, 0010
- **Blocks**: v0.1.0
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

The MVP works locally. Before the first public push it needs a production image, a README a stranger can
follow, an architecture page, the research notes in English, and a release gate that proves the
repository is clean.

## 2. User stories

- As a visitor, I want to understand what the project does and how good it is in one screen.
- As a user, I want to run it with uv or with Docker, locally or as production jobs.

## 3. Applicable rules

- `RULE-DATA-01`: no data, no `.env`, no licensed content in the image or the repository.

## 4. Contracts and data model

- `Dockerfile` targets `build` and `runtime`: the package and its runtime dependencies in `/opt/venv`, a
  non-root user, `QMAS_DATA_DIR=/data` as a volume, `qmas` as entry point.
- `compose.prod.yml`: one-off jobs on the runtime image, named volume `qmas-data`, read-only root file
  system, `tmpfs` for `/tmp`, all capabilities dropped, `no-new-privileges`.
- Version `0.1.0`; CHANGELOG release section.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| Docker | `docker compose -f compose.prod.yml run --rm qmas <command>` | Production jobs. |

## 6. Acceptance criteria

- [ ] README: what it does, results, architecture, requirements, setup, configuration table, usage with
      example output, Docker local and production, data sources (recommended and free), tests,
      structure, limitations, disclaimer.
- [ ] `docs/architecture.md`, `docs/research/methodology.md`, `prior-study-catalysts.md`, `roadmap.md`.
- [ ] Production image builds, runs as non-root, and runs E1 quick and a thesis on a read-only file system.
- [ ] Release gate: `poe check` locally and in Docker, a clean clone works without `.env`, gitleaks
      finds nothing, the private denylist finds nothing, `git ls-files` holds no data or large file.

## 7. Required tests

The existing suite; the release gate above is the verification.

## 8. Out of scope

- Publishing to a registry; CI (checks run locally by design).
