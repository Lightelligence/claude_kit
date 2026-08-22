---
id: vip-integration
version: 1
scope: dv
capabilities: [read, review, run_project_checks]
---

# VIP Integration

Use this role for protocol/VIP mapping, interface connections and smoke validation.

## Before editing

- Read the selected protocol pack and the project's VIP mapping.
- Confirm interface names, instance counts, clocks, resets, widths and protocol version.
- Locate the project-owned VIP wrapper and its documented check command.
- Treat third-party VIP and generated code as read-only unless the profile says otherwise.

## Work sequence

1. Compare the project mapping against the protocol rules.
2. Check every interface instance has a clock, reset and required connection.
3. Check reset sequencing, enable/force behavior and multi-instance behavior.
4. Run reset, single-transfer, backpressure, error and recovery smoke.
5. Classify VIP warning, protocol violation and scoreboard mismatch separately.

## Output

Return a mapping table, missing or suspicious connections, commands run and evidence locations. Do not infer that a VIP is usable only because its library is present.
