---
name: rtl-dv-regression
version: 1
description: Select and triage focused-to-regression RTL/DV checks through declared project wrappers, with explicit execution approval and reproducible evidence.
---

# RTL/DV Regression

Use the `regression-triager` role for analysis and selection when a task involves
compile, elaboration, simulation, a regression, a Bazel target, a verification
service or a result set that must be compared. Use `commander` only for a run
that the user explicitly approved or delegated.

1. Reuse current routing and check choices; use `plan_task` only when unclear.
   Inspect the current check catalog (`list_catalog(category="checks")` in
   compact MCP mode) if needed. Present unresolved choices to the engineer;
   a recommended quick check is not automatic permission.
2. Bind each run to source revision, target, test selector, seed, simulator,
   working directory and artifact locations.
3. Start with the cheapest check that can distinguish environment, compile,
   elaboration, runtime, protocol, assertion, scoreboard, timeout and coverage
   failures among the engineer's selected checks. A newly created or modified
   DV test does not authorize simulation or regression.
4. Preserve the first causal error and the exact command; do not treat a clean
   exit or a generated report as proof without checking expected results.
5. After explicit approval or `commander` delegation, invoke the registered
   project MCP tool if project policy requires MCP. Do not use a shell fallback
   when it is unavailable. A declared wrapper is usable only where project
   policy permits it. Rerun or expand only within the engineer's selection;
   ask before adding a regression slice.
6. Keep license, remote-runner, resource and missing-artifact problems explicit
   as blocked or environment results.

When a profile declares an external regression root, call the read-only
`discover_regression_artifacts` tool after a project MCP check returns. Bind
the returned directory and log to the exact target, test and run id. If more
than one run matches, ask the engineer to select one; do not choose by
modification time. Read logs only through `read_regression_artifact` and keep
lock files visible as an in-progress signal.

Use project-permitted interfaces and profile allowlists. Keep logs,
waveforms, reports and coverage artifacts; do not perform cleanup as part of
triage. For multiple selected checks, preserve order and return an individual
report and aggregate result counts.
