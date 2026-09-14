---
name: rtl-dv-context
version: 1
description: Resolve missing project facts or select bounded RTL/DV context when the task's scope is unclear.
---

# RTL/DV Context

Use the project's configured claude-kit installation, whether shared or pinned
as a submodule. Prefer its registered MCP bridge in a Claude Code session;
the CLI provides the same planning and inspection functions for maintenance.

Start from the facts already available in this session. Read only what is missing
or stale; do not rebuild context solely because another file needs editing.

- Read `get_project_profile` when configuration or permissions are unknown or
  changed (CLI: `claude-kit doctor`). Resolve relevant validation errors before
  relying on that configuration.
- Use `plan_task` when workflow, role or check selection is unclear (CLI:
  `claude-kit plan --task "..."`). A plan does not authorize its suggested checks.
- Before execution, resolve the required target, test, simulator and revision
  from authoritative project facts. A read-only inspect can answer a specific
  missing fact; it is not a mandatory extra call for every edit.
- Select only relevant role and protocol/VIP guidance. Generate context and a
  manifest when a handoff or reproducible context artifact is needed, not merely
  because the task touches several files.

Kit role names identify guidance, not proof that a same-named Claude subagent
is installed. Use an available project agent when appropriate, or apply the
role guidance in the current session; do not invent an unavailable agent.

Keep project facts in the profile rather than copied prompts. Preserve project
permissions and check-selection gates. Record the source revision, actual
commands/results and unresolved risks when reporting verification evidence.
