---
name: rtl-dv-evidence
version: 1
description: Record reproducible RTL/DV checks, artifacts and unresolved risks before handoff, review or sign-off.
---

# RTL/DV Evidence

Use this skill when a task changes files, runs a project check, prepares a handoff, or claims verification.

1. Run `claude-kit plan --task "..."` and carry its workflow, selected
   roles/skills/packs, check plan and warnings into the evidence review.
2. Freeze identity: record the project, task, source revision, selected
   role/pack, test, seed, simulator and working directory.
3. Enumerate changes with project-relative paths and a short reason for every changed file.
4. Record each check with its exact argv, status, exit result and relevant artifact path. Use `claude-kit artifact read` for a bounded log excerpt.
5. Separate passed, failed, skipped, blocked and unknown checks; state the reason for every skipped or blocked check.
6. Record residual risks, coverage gaps and environment or license prerequisites without converting them into a pass.
7. Run `claude-kit evidence check --strict` against the final evidence file and fix every reported error.

Completion means the evidence file matches the current project and task, every claimed check has execution evidence or an explicit exception, changed paths are inside the writable scope, and strict evidence validation passes.
