---
name: rtl-dv-context
version: 1
description: Resolve the project profile and smallest useful RTL/DV context before acting.
---

# RTL/DV Context

Use the pinned repo-local claude-kit CLI before changing project files.

1. Run doctor and stop on permission or profile errors.
2. Run inspect or a read-only project command first.
3. Select one primary role and only the protocol/VIP packs needed for the task.
4. Generate a context and manifest when the task spans multiple files.
5. Keep project facts in the profile, not in a copied global prompt.
6. Record the source revision, commands, results and unresolved risks.
