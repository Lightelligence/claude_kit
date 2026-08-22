---
name: rtl-design
version: 1
description: Plan and implement bounded RTL changes with reset, handshake and evidence checks.
---

# RTL Design

Use rtl-architect for design decisions and rtl-designer for bounded edits.

- Read the profile, local rules, module, interface and focused tests first.
- State the invariant and acceptance condition before editing.
- Check reset, state-machine defaults, widths, signedness, FIFO boundaries and error recovery.
- For valid/ready paths, check payload stability, no duplicate transfer and no lost transfer.
- Make the smallest coherent edit in writable paths.
- Run the cheapest relevant project check before expanding validation.
- Never report simulation as passed when it was not run.
