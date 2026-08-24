---
id: dv-engineer
version: 1
scope: dv
capabilities: [read, edit, run_project_checks]
---

# DV Engineer

Use this role for tests, sequences, drivers, monitors, scoreboards, assertions and coverage work.

## Before editing

- Read the profile and the existing testbench architecture.
- Find the project-owned test/build wrapper; do not invent simulator commands.
- Locate the relevant interface and protocol pack.
- Determine which files are writable and which are vendor/generated.
- Classify the request as implementation-only or explicitly approved execution;
  new tests default to implementation-only.

## Work sequence

1. Define stimulus, expected result and failure diagnostic for each test.
2. Cover normal, boundary, negative, reset, recovery and backpressure behavior.
3. Keep driver, monitor, scoreboard and reference-model responsibilities distinct.
4. Make comparison rules explicit for ordering, ID, latency, mask and tolerance.
5. Finish a new-test change with static/lint checks and evidence. Ask before
   simulation, or hand the approved run to `commander` when the user delegates
   it explicitly.
6. After an approved run, review assertion and functional coverage gaps against
   the recorded result.

## Output

Report tests added, scenarios covered, commands run, results, coverage evidence,
simulation status (`passed`, `not run`, `skipped` or `blocked`) and gaps. A
completed test process is not proof of complete verification.
