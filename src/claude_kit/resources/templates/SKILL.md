---
name: rtl-dv-kit
description: Use the repo-local claude-kit profile, roles, protocol/VIP packs and evidence workflow for RTL/DV work.
---

# RTL/DV Claude Kit

Before changing project files:

1. Locate and validate .ai/project.toml with claude-kit doctor.
2. Run a read-only inspect or context command first.
3. Select the smallest relevant role and protocol/VIP pack.
4. Respect the project's writable, read_only and forbidden paths.
5. Use project commands declared in build.commands; do not invent simulator commands.
6. Report changed files, commands, results, skipped checks and unresolved risks.
7. Never claim verification without execution evidence.
