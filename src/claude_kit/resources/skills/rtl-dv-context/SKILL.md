---
name: rtl-dv-context
version: 1
description: Resolve the project profile and smallest useful RTL/DV context before acting.
---

# RTL/DV Context

Use the pinned repo-local claude-kit CLI before changing project files.

1. Run doctor and stop on permission or profile errors.
2. Run `claude-kit plan --task "..."` to select the workflow, primary role, skills and declared checks.
3. Resolve missing target, test, simulator and source-revision facts before execution.
4. Run inspect or a read-only project command first.
5. Select one primary role and only the protocol/VIP packs needed for the task.
6. Generate a context and manifest when the task spans multiple files.
7. Keep project facts in the profile, not in a copied global prompt.
8. Record the source revision, commands, results and unresolved risks.
