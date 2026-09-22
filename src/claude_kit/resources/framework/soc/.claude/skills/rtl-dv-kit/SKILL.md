---
name: rtl-dv-kit
description: Locate the project's Claude kit configuration and execution contract for RTL/DV work.
---

# RTL/DV Claude Kit

Use the configured project profile (normally `.claude/project.toml`) as the source
of project facts and permissions. Respect writable, read_only and forbidden
paths; declared `hw/**` is normal RTL/DV work scope, not inherently protected.

Prefer the registered kit MCP in Claude Code; the repo-local CLI is also a
maintenance entrypoint. If configuration is missing, changed or unvalidated,
use `get_project_profile` (CLI: `doctor`) before relying on it. Resolve relevant
validation errors; do not repeat discovery when current facts are already known.

Use `plan_task` when workflow or check selection is unclear. Read only the
selected skill/role/protocol guidance needed for this task. A straightforward
edit with known context does not require a doctor/plan/inspect sequence.

Execute only the requested checks through registered project tools or declared
`build.commands`, subject to the project's execution contract. Do not invent
simulator commands or auto-run simulation, regression, coverage, synthesis or
CDC after an edit. Resolve required inputs and permissions before execution.

Report changed files, executed commands, results, skipped checks and unresolved
risks. A plan or successful registration is not verification evidence.
