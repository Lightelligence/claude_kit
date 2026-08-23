---
name: rtl-dv-debugging
version: 1
description: Debug compile, simulation, assertion, scoreboard, timeout and coverage failures from evidence.
---

# RTL/DV Debugging

1. Run `claude-kit plan --workflow debug --task "..."` and use the
   `debugger`, `waveform-debugger` and `regression-triager` roles as applicable.
2. Capture the exact command, cwd, source revision, target, test, seed,
   simulator and first meaningful error; confirm the artifact belongs to that
   run.
3. Separate environment, compile, elaboration/link, runtime, protocol,
   assertion, scoreboard, coverage and timeout failures.
4. Reduce to a single test, seed, transaction, cycle or minimal reproducer and
   state a falsifiable root-cause hypothesis.
5. Rerun the smallest reproducer after a fix, then expand only to the
   regression slice supported by evidence.
6. Preserve before/after evidence and state blocked external prerequisites
   explicitly. Do not turn a clean exit or incomplete waveform into a pass.
