---
name: rtl-dv-kit
description: Use the repo-local claude-kit profile, roles, protocol/VIP packs and evidence workflow for RTL/DV work.
---

# RTL/DV Claude Kit

Before changing project files:

1. Locate and validate .ai/project.toml with claude-kit doctor.
2. Run `claude-kit plan --task "..."` and treat missing facts or command warnings as gates.
3. Load only the selected skills with `context --skill <id>` when their guidance is needed.
4. Run a read-only inspect or context command before edits.
5. Select the smallest relevant role and protocol/VIP pack.
6. Respect the project's writable, read_only and forbidden paths.
7. Use project commands declared in build.commands; do not invent simulator commands.
8. Report changed files, commands, results, skipped checks and unresolved risks.
9. Never claim verification without execution evidence.
