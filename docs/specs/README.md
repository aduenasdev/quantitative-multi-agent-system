# Spec convention

A spec is the contract between whoever decides what to build and whoever builds it (a person or an AI
coding agent). Its job is to remove ambiguity, not to document everything: if the implementer still has to
guess something important after reading it, the spec failed.

## Hard rules

1. One spec is one self-contained slice that can be merged on its own. Two merges means two specs.
2. A spec cites the governance rules it applies (`RULE-*` in [../rules.md](../rules.md)); it never redefines them.
3. Acceptance criteria are a checklist. The spec is done when every item is ticked.
4. Out of scope is explicit: what this spec does **not** do, even if it looks related.
5. Tests are part of the spec. Without tests a spec is not done.
6. A spec longer than about 200 lines is too big: split it.
7. An approved spec does not change silently during implementation. New findings go to
   "Post-implementation notes" or to a new spec.

## Files and states

- Template: [TEMPLATE.md](TEMPLATE.md). Index with status and dependencies: [INDEX.md](INDEX.md).
- Specs live in `pending/` while they are `draft`, `ready` or `in-progress`, and move to `done/` when `done`.
- File name: `NNNN-short-title.md`. Numbers are never reused.

| State | Meaning |
|---|---|
| `draft` | Being written; not ready to implement. |
| `ready` | Reviewed; can be implemented. |
| `in-progress` | On its branch. |
| `done` | Merged into `main` with every criterion ticked. |
| `superseded` | Replaced by another spec (named in the header). |

## Workflow

1. Branch from an up-to-date `main`: `git switch -c feat/spec-NNNN-short-title`.
2. Set the spec to `in-progress` and list the files you will touch.
3. Implement with tests alongside the code, never 200 lines without a test.
4. Tick acceptance criteria as they are met.
5. Run `uv run poe check`; it must pass.
6. Commit with Conventional Commits that name the spec: `feat(NNNN): ...`, `fix(NNNN): ...`,
   `test(NNNN): ...`, `docs(NNNN): ...`, `refactor(NNNN): ...`, `chore(NNNN): ...`.
7. Set the spec to `done`, move it to `done/`, update [INDEX.md](INDEX.md).
8. Merge into `main` with `git merge --no-ff` and delete the branch.

Out-of-scope discoveries are written down in the spec ("Post-implementation notes") and handled in a new spec,
never in the current branch.
