---
name: rtl-dv-regression
version: 1
description: Select and triage focused-to-regression RTL/DV checks through declared project wrappers with reproducible evidence.
---

# RTL/DV Regression

Use the `regression-triager` role when a task involves compile, elaboration,
simulation, a regression, a Bazel target, a verification service or a result
set that must be compared.

1. Run `claude-kit plan` for the task and inspect the profile's declared
   commands before executing anything.
2. Bind each run to source revision, target, test selector, seed, simulator,
   working directory and artifact locations.
3. Start with the cheapest check that can distinguish environment, compile,
   elaboration, runtime, protocol, assertion, scoreboard, timeout and coverage
   failures.
4. Preserve the first causal error and the exact command; do not treat a clean
   exit or a generated report as proof without checking expected results.
5. Rerun the smallest reproducer after a fix, then expand only to the smallest
   regression slice supported by evidence.
6. Keep license, remote-runner, resource and missing-artifact problems explicit
   as blocked or environment results.

Use project-owned wrappers and profile allowlists. Keep logs, waveforms,
reports and coverage artifacts; do not perform cleanup as part of triage.
