# Shared Claude Kit Rules

This file is shared by projects that pin claude_kit.

- The project profile is the source of truth for roots, commands, permissions and artifacts.
- For RTL/DV projects, `hw/**` is a normal implementation scope when `[roots].hw` and `permissions.writable` declare it; do not assume other paths are writable.
- Use `permissions.writable` for ordinary edits. For deliberate cleanup, declare the exact obsolete path under `permissions.deletable` and record the evidence change as `{\"path\": \"...\", \"operation\": \"delete\"}`; read-only and forbidden scopes still override both.
- Reuse current project facts and task context. Inspect only missing or stale information.
- Prefer registered kit MCP tools in Claude Code. Use `plan_task` only when workflow or check selection is unclear; resolve missing facts before the affected operation, not as a blanket gate for unrelated edits.
- Load only missing skill/role/protocol guidance through native skills or `resolve_context`; do not load the same guidance twice. Pass empty roles/packs when profile defaults are unnecessary. CLI plan/context are maintenance equivalents, not extra steps.
- Treat a new or modified DV test as an implementation task first: finish planning, edits, static/lint checks and evidence before execution.
- Simulation and regression require an explicit selection or delegation. Reuse existing approval for that exact scope; ask with command, target, test, cost and artifacts only when authorization is missing or scope expands. `commander` is not an automatic follow-up.
- Mark simulation as `not run`, `skipped` or `blocked` when it has not started; reserve `passed` for a run with matching evidence.
- Keep project-specific paths and target names in the project profile or adapter.
- If the profile declares an external provider such as `xverif` and that server is registered in Claude Code, use the provider's registered MCP tools for its capability; do not replace them with ad-hoc Python, shell, or guessed simulator commands.
- For xdebug work, call `xverif_tools` once, then `xverif_debug_get_schema`, then use the managed session/query lifecycle. Keep xverif's source-only and separately licensed runtime boundary explicit.
- When a project profile declares `[artifacts.regression]`, use the read-only
  `discover_regression_artifacts` MCP tool to locate compile/simulation logs
  and `read_regression_artifact` to inspect a bounded log. Do not scan a
  regression parent directory or infer the newest run; require an explicit
  target/test/run selection when multiple matches are returned.
- Do not modify vendor, generated, build or .git content unless the profile explicitly allows it.
- After an implementation or DV environment change, use the known check menu or fetch `list_catalog(category="checks")` (compact MCP), `list_checks` (full MCP), or CLI `checks` when missing/stale. Show unresolved choices, not a second approval for checks already selected. Never auto-select simulation, regression, coverage, synthesis or CDC.
- For a profile entry with `execution = "mcp"`, call its registered `mcp_server`/`mcp_tool` through Claude Code. Do not replace it with Bash, Python or a hand-built Bazel command. Use `argv` only for profile entries explicitly declared as shell wrappers.
- When the engineer selects multiple checks, preserve the selected order, invoke every selected MCP tool or approved wrapper, and return one result report per check plus aggregate passed/failed/blocked/not-run counts.
- Do not invent or concatenate simulator commands.
- Record evidence for every check and mark blocked or skipped checks explicitly.
- Do not expose secrets in context, manifests or logs.
- The kit does not depend on ETX runner, bsub or a specific scheduler.
