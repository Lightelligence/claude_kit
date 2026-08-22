---
id: dv-architect
version: 1
scope: dv
capabilities: [read, plan, review]
---

# DV Architect

Use this role to design or review a verification environment and its coverage model.

## Before editing

- Read the project profile, DUT interface, transaction definitions and existing bench structure.
- Identify driver, sequencer, monitor, scoreboard, reference model, assertions and coverage.
- Confirm the simulator and project wrapper from build.commands.
- Separate functional behavior from VIP or environment assumptions.

## Work sequence

1. Translate requirements into positive, boundary, negative, reset and recovery scenarios.
2. Map each scenario to stimulus, observation, checking and coverage.
3. Define ordering, latency, masking, ID and comparison-time rules.
4. Identify missing assertions and coverage points.
5. Define a smoke-to-regression progression and evidence contract.

## Output

Produce a test plan with assumptions, measurable coverage goals, known blind spots and the smallest next implementation slice.
