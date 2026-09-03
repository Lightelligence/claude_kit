---
name: rtl-dv-context
version: 1
description: Resolve the project profile and smallest useful RTL/DV context before acting.
---

# RTL/DV Context

Use the project's configured claude-kit installation, whether shared or pinned
as a submodule. Prefer its registered MCP bridge in a Claude Code session;
the CLI provides the same planning and inspection functions for maintenance.

1. Read `get_project_profile` and stop on validation errors (CLI: `claude-kit doctor`).
2. Use `plan_task` to select the workflow, primary role, skills and declared checks (CLI: `claude-kit plan --task "..."`).
3. Resolve missing target, test, simulator and source-revision facts before execution.
4. Run inspect or a read-only project command first.
5. Select one primary role and only the protocol/VIP packs needed for the task.
6. Generate a context and manifest when the task spans multiple files.
7. Keep project facts in the profile, not in a copied global prompt.
8. Record the source revision, commands, results and unresolved risks.
