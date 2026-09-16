---
name: rtl-dv-debugging
version: 1
description: Diagnose RTL/DV compile, runtime, assertion, scoreboard, timeout or coverage failures from bounded evidence. Fixes and new runs require the corresponding task authorization.
---

# RTL/DV Debugging

## Bind the failure

Start from known failure context. Use `plan_task` only when routing is unclear.
Capture available invocation, source revision/dirty state, cwd, target/test/seed,
simulator/configuration, run ID and first meaningful error. Verify artifacts belong
to that run, not merely the current checkout or newest directory. Missing identity
limits the conclusion; it need not block all independent analysis.

Diagnose is read-only by default. A request to explain a log does not authorize
source changes, instrumentation, waveform regeneration, simulation or cleanup.
If the task explicitly includes a fix, make a minimal supported change in writable
scope; rerun/expansion still follows the engineer's selected execution scope.
Roles such as debugger or waveform-debugger are guidance, not automatic subagents
or authority to bypass these boundaries.

## Investigate causality

Read [Failure investigation](references/investigation.md) for the relevant symptom.
Classify environment/license/resource, compile, elaboration/link, runtime, protocol,
assertion, scoreboard, timeout and coverage issues without prematurely blaming RTL.
Separate direct observations, inferences and untested hypotheses.

Reduce the existing evidence to one test/seed, transaction, cycle or state transition.
This means narrowing analysis, not automatically running a new reproducer. State
a falsifiable hypothesis and the observation that would distinguish alternatives.
Trace surrounding guards, reset/sampling conditions and expected behavior before
naming a root cause. Do not treat matching error text as proof of identical causes.

## Tools and validation

Read small log regions first. For existing waveforms/design databases use the
enabled debug MCP's schema and managed sessions only when needed. Query bounded
signals/time windows; preserve database identity and close only task-owned sessions.
Unavailable data or optimized-away signals are gaps, not zero values or proof of
absence. Do not infer unseen internal signal values.

Propose the smallest confirming check with target/test/seed and expected evidence.
Run only selected checks through the project interface; MCP-only policy forbids a
shell fallback. Reuse explicit approval within scope and check remote job state
before retrying a timed-out call. No automatic regression, coverage or CDC expansion.

## Report

Lead with supported cause or the remaining alternatives, confidence/evidence,
first causal location/time, expected versus observed behavior and discriminating
next check. When a fix is authorized, include changed files and before/after results
(or not-run/blocked status). Preserve original failures and label environmental or
flaky outcomes; neither a code change nor incomplete trace proves a successful fix.
