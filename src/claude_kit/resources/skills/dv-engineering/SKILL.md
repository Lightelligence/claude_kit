---
name: dv-engineering
version: 1
description: Plan and implement focused RTL/DV tests with explicit scenarios and evidence.
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
4. Run one focused test through a profile-declared wrapper before requesting a
   larger regression. Use `rtl-dv-regression` for the focused-to-regression
   expansion and preserve the first causal failure.
5. Separate stimulus gaps, sampling gaps, DUT failures, environment failures
   and coverage gaps.
6. Report tests changed, scenarios covered, assertions, coverage, exact
   commands/results, skipped or blocked checks and remaining blind spots.
