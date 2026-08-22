---
name: rtl-dv-evidence
version: 1
description: Record reproducible RTL/DV checks, artifacts and unresolved risks before handoff, review or sign-off.
---

# RTL/DV Evidence

Use this skill when a task changes files, runs a project check, prepares a handoff, or claims verification.

1. Freeze identity: record the project, task, source revision, selected role/pack, test, seed, simulator and working directory.
2. Enumerate changes with project-relative paths and a short reason for every changed file.
3. Record each check with its exact argv, status, exit result and relevant artifact path. Use `claude-kit artifact read` for a bounded log excerpt.
4. Separate passed, failed, skipped, blocked and unknown checks; state the reason for every skipped or blocked check.
5. Record residual risks, coverage gaps and environment or license prerequisites without converting them into a pass.
6. Run `claude-kit evidence check --strict` against the final evidence file and fix every reported error.

Completion means the evidence file matches the current project and task, every claimed check has execution evidence or an explicit exception, changed paths are inside the writable scope, and strict evidence validation passes.
