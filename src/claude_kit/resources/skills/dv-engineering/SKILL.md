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
   start simulation automatically.
5. When a focused simulation is useful, ask for explicit approval with the
   command, target, test selector, expected cost and artifact location. After
   approval, or after explicit delegation to `commander`, run one focused test
   through a profile-declared wrapper before requesting a larger regression. Use
   `rtl-dv-regression` for the focused-to-regression expansion and preserve the
   first causal failure.
6. Separate stimulus gaps, sampling gaps, DUT failures, environment failures
   and coverage gaps.
7. Report tests changed, scenarios covered, assertions, coverage, exact
   commands/results, skipped or blocked checks and remaining blind spots.

## Simulation gate

- Default new-test handoff: simulation and regression are `not run`.
- Approval request: name the profile command, target, test selector, simulator,
  expected runtime/resource cost and artifact destination.
- `commander` is an explicit execution role, not a default follow-up. It uses
  only profile-declared wrappers and preserves the command, source revision,
  logs and result evidence.
- A simulation or regression result is `passed` only when the command ran and
  its expected artifacts and checks are present.
