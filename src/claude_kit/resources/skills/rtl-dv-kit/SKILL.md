---
name: rtl-dv-kit
description: Resolve missing RTL/DV project facts, permissions or workflow choices; not a mandatory preflight for known tasks.
---

# RTL/DV Claude Kit

Use the project's discovered profile (`.claude/project.toml` or legacy
`.ai/project.toml`) for roots, permissions, target mappings and tool routing.
Declared writable `hw/**` is normal RTL/DV implementation scope. Respect
read-only and forbidden paths, and preserve unrelated work.

Reuse facts already known in this session. Prefer registered kit MCP tools:

- `get_project_profile` when configuration is missing, stale or unvalidated.
  Resolve relevant errors before relying on it, not before unrelated work.
- `plan_task` when workflow or check selection is unclear. A known file edit
  does not need a profile/plan/inspect sequence.
- `resolve_context` only for missing skill, role or protocol guidance or a
  reproducible handoff. Select the needed IDs; pass `roles=[]` and `packs=[]`
  when their profile defaults are unnecessary. Do not reload a native skill
  already present in the session.

Kit roles are guidance, not proof that a same-named subagent exists. Use an
available project agent or apply the guidance in the current session.

Execute only selected checks through the project's registered tools or
explicitly permitted wrappers. A plan does not authorize execution. Reuse
the engineer's existing approval for that exact scope; ask only for unresolved
choices or expanded scope. Never auto-add simulation, regression, coverage,
synthesis or CDC to an implementation task. RTL-only lint is not DV validation.

Bind target/test, revision, simulator and artifacts before the operation that
needs them. Report actual checks and remaining gaps; registration or a plan is
not verification evidence. Use `rtl-dv-evidence` for a formal evidence package
when requested or required by project policy, not for every small edit.
