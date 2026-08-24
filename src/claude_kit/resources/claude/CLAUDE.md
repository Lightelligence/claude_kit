# Shared Claude Kit Rules

This file is shared by projects that pin claude_kit.

- The project profile is the source of truth for roots, commands, permissions and artifacts.
- For RTL/DV projects, `hw/**` is a normal implementation scope when `[roots].hw` and `permissions.writable` declare it; do not assume other paths are writable.
- Start with read-only inspection and context resolution.
- Run the repo-local `claude-kit plan --task "..."` first when selecting an RTL/DV workflow; treat its missing facts and warnings as gates.
- Load only the selected skill guidance with `claude-kit context --skill <id>` or the equivalent MCP `resolve_context.skills` request.
- Use a role for the task and load only the protocol/VIP packs that apply.
- Treat a new or modified DV test as an implementation task first: finish planning, edits, static/lint checks and evidence before execution.
- Simulation and regression are explicit-consent steps. Ask for approval with the selected command, target, test, expected cost and artifacts, or use the `commander` role only when the user explicitly delegates that run.
- Mark simulation as `not run`, `skipped` or `blocked` when it has not started; reserve `passed` for a run with matching evidence.
- Keep project-specific paths and target names in the project profile or adapter.
- Do not modify vendor, generated, build or .git content unless the profile explicitly allows it.
- Use argv from build.commands; do not invent or concatenate simulator commands.
- Record evidence for every check and mark blocked or skipped checks explicitly.
- Do not expose secrets in context, manifests or logs.
- The kit does not depend on ETX runner, bsub or a specific scheduler.
