---
name: dv-engineering
version: 1
description: Plan and implement focused RTL/DV tests with explicit scenarios, static validation, and an approval gate before simulation.
---

# DV Engineering

Use dv-architect for the verification plan and dv-engineer for testbench edits.

1. Run `claude-kit plan --workflow dv-change --task "..."` and bind the
   source revision, target, test selector, simulator and artifact locations.
2. Map requirements to positive, boundary, negative, reset and recovery
   scenarios before writing stimulus.
3. Keep driver, monitor, scoreboard, reference model and coverage
   responsibilities distinct; define ordering, ID, masking, latency and
   comparison-time rules.
4. Complete the implementation phase with profile validation, read-only
   inspection, static/lint checks and evidence. A new or modified test does not
   start simulation automatically. Then call the profile check menu and present
   the engineer with suggested quick checks and separately marked explicit
   simulation, regression, coverage, synthesis and CDC choices.
5. When a focused simulation is useful, ask for explicit approval with the
   command, target, test selector, expected cost and artifact location. After
   approval, or after explicit delegation to `commander`, run one focused test
   through the registered project MCP tool when the profile says `execution =
   "mcp"`; otherwise use the explicitly declared wrapper. Before requesting a
   larger regression, preserve the first causal failure. Use
   `rtl-dv-regression` for focused-to-regression expansion.
6. Separate stimulus gaps, sampling gaps, DUT failures, environment failures
   and coverage gaps.
7. Report tests changed, scenarios covered, assertions, coverage, exact
   commands/results, skipped or blocked checks and remaining blind spots.

## Simulation gate

- Default new-test handoff: simulation and regression are `not run`.
- Approval request: name the profile command, target, test selector, simulator,
  expected runtime/resource cost and artifact destination.
- `commander` is an explicit execution role, not a default follow-up. It uses
  only profile-declared wrappers or registered MCP tools and preserves the
  selected tool, source revision, logs and result evidence.
- For a multi-selection, keep the engineer's order and report every selected
  item, including blocked or not-run items; do not silently drop expensive
  categories.
- A simulation or regression result is `passed` only when the command ran and
  its expected artifacts and checks are present.
