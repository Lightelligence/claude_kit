---
name: protocol-vip
version: 1
description: Apply the smallest matching protocol/VIP pack and validate connection and smoke behavior.
---

# Protocol and VIP

1. Reuse known task context; use `plan_task` only if routing is unclear.
   Select the protocol pack after confirming the exact version and layer.
2. Read the selected pack and the project's VIP mapping. Keep VIP class names,
   library paths, macros, licenses and simulator settings project-local.
3. Build a mapping for every instance: clock, reset, direction, width,
   endpoint, configuration and generated/vendor boundary.
4. Propose applicable reset, legal-transfer, backpressure, error and recovery
   smoke checks. Run only checks the engineer selected, through the project's
   required execution interface. A mapping edit does not authorize simulation;
   an MCP-only project has no direct wrapper or simulator fallback.
5. Classify VIP warnings, protocol violations, scoreboard mismatches and
   environment failures separately; do not infer usability from library
   presence or process exit alone.
6. Record the protocol pack/version, mapping assumptions, exact checks and
   missing coverage or blocked prerequisites.
