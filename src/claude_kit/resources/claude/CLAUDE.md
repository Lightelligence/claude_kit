# Shared Claude Kit Rules

This file is shared by projects that pin claude_kit.

- The project profile is the source of truth for roots, commands, permissions and artifacts.
- Start with read-only inspection and context resolution.
- Run the repo-local `claude-kit plan --task "..."` first when selecting an RTL/DV workflow; treat its missing facts and warnings as gates.
- Load only the selected skill guidance with `claude-kit context --skill <id>` or the equivalent MCP `resolve_context.skills` request.
- Use a role for the task and load only the protocol/VIP packs that apply.
- Keep project-specific paths and target names in the project profile or adapter.
- Do not modify vendor, generated, build or .git content unless the profile explicitly allows it.
- Use argv from build.commands; do not invent or concatenate simulator commands.
- Record evidence for every check and mark blocked or skipped checks explicitly.
- Do not expose secrets in context, manifests or logs.
- The kit does not depend on ETX runner, bsub or a specific scheduler.
