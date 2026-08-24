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

1. Run `claude-kit plan` for the task and inspect `list_checks`/`checks` and the
   profile's declared commands before executing anything. Present the menu to
   the engineer; a recommended quick check is not automatic permission.
2. Bind each run to source revision, target, test selector, seed, simulator,
   working directory and artifact locations.
3. Start with the cheapest check that can distinguish environment, compile,
   elaboration, runtime, protocol, assertion, scoreboard, timeout and coverage
   failures. For a newly created or modified DV test, finish static/lint
   validation and pause before simulation or regression.
4. Preserve the first causal error and the exact command; do not treat a clean
   exit or a generated report as proof without checking expected results.
5. After explicit approval or `commander` delegation, invoke the registered
   project MCP tool when the selected check is MCP-backed; otherwise run the
   declared wrapper. Rerun the smallest reproducer after a fix, then expand
   only to the smallest regression slice supported by evidence.
6. Keep license, remote-runner, resource and missing-artifact problems explicit
   as blocked or environment results.

Use project-owned MCP tools or wrappers and profile allowlists. Keep logs,
waveforms, reports and coverage artifacts; do not perform cleanup as part of
triage. For multiple selected checks, preserve order and return an individual
report and aggregate result counts.
