---
name: rtl-dv-debugging
version: 1
description: Debug compile, simulation, assertion, scoreboard, timeout and coverage failures from evidence.
---

# RTL/DV Debugging

1. Reuse known failure context; use `plan_task` only if routing is unclear.
   Select debugger, waveform or regression guidance only as needed.
2. Capture the exact command, cwd, source revision, target, test, seed,
   simulator and first meaningful error; confirm the artifact belongs to that
   run.
3. Separate environment, compile, elaboration/link, runtime, protocol,
   assertion, scoreboard, coverage and timeout failures.
4. Reduce to a single test, seed, transaction, cycle or minimal reproducer and
   state a falsifiable root-cause hypothesis.
5. After a fix, propose the smallest reproducer. Rerun or expand only within
   the engineer's explicit selection and the project's execution interface;
   diagnosing an existing log does not authorize a new simulation.
6. Preserve before/after evidence and state blocked external prerequisites
   explicitly. Do not turn a clean exit or incomplete waveform into a pass.
