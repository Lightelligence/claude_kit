---
name: rtl-design
version: 1
description: Plan and implement bounded RTL changes with reset, handshake and evidence checks.
---

# RTL Design

Use rtl-architect for design decisions and rtl-designer for bounded edits.

1. Run `claude-kit plan --task "..."` and use its selected role, skill,
   pack, check plan and missing-fact warnings as the task contract.
2. Resolve the profile, local rules, module, interface and focused tests before
   editing; use `claude-kit context --skill rtl-design` when the skill text is
   not already materialized in the project.
3. State the invariant, observable acceptance condition and affected checks.
4. Check reset, state-machine defaults, widths, signedness, FIFO boundaries
   and error recovery. For valid/ready paths, check payload stability, no
   duplicate transfer and no lost transfer.
5. Make the smallest coherent edit in writable paths and review the diff for
   vendor/generated or unrelated changes.
6. Run the cheapest relevant project check before expanding validation.
7. Return changed paths, invariant, commands, results, skipped/blocked checks
   and residual risks. Never report simulation as passed when it was not run.
