---
name: rtl-dv-evidence
version: 1
description: Record reproducible RTL/DV checks, artifacts and unresolved risks before handoff, review or sign-off.
---

# RTL/DV Evidence

Use this skill when a task changes files, runs a project check, prepares a handoff, or claims verification.

1. Reuse the task's actual workflow, selected roles/packs, checks and warnings.
   Use `plan_task` only for unresolved routing, not to recreate known context.
2. Freeze identity: record the project, task, source revision, selected
   role/pack, test, seed, simulator and working directory.
3. Enumerate changes with project-relative paths and a short reason for every changed file. Use ordinary path strings for edits; represent a deliberate cleanup deletion as `{\"path\": \"...\", \"operation\": \"delete\"}` and confirm the exact path is in `permissions.deletable`.
4. Record each check with its exact argv, status, exit result and relevant artifact path. Use `read_artifact` for checkout-local logs, or use `discover_regression_artifacts` followed by `read_regression_artifact` for configured external compile/simulation logs.
5. Separate passed, failed, skipped, blocked and unknown checks; state the reason for every skipped or blocked check.
6. Record residual risks, coverage gaps and environment or license prerequisites without converting them into a pass.
7. Use the registered `review_evidence` tool with strict validation for the
   final evidence file and resolve reported errors. The CLI maintenance
   equivalent is `claude-kit evidence check --strict`; engineers do not need
   to run it manually inside an ordinary Claude Code conversation.

Completion means the evidence file matches the current project and task, every claimed check has execution evidence or an explicit exception, ordinary changes are inside `permissions.writable`, audited deletions are inside `permissions.deletable`, and strict evidence validation passes.
