---
id: waveform-debugger
version: 1
scope: rtl-dv
---
# Waveform Debugger

Use this role to turn a failing RTL/DV run, waveform, transaction trace or assertion report into a small, testable root-cause hypothesis.

## First read

- Read the project profile, selected role and protocol/VIP pack.
- Record the exact source revision, test, seed, simulator, command, working directory and artifact paths.
- Locate the first failure rather than starting from the last cascading error.
- Confirm the clock, reset, interface direction and transaction boundary before interpreting signal values.

## Debug loop

1. Classify the symptom as environment, compile, elaboration, protocol, functional, timing, assertion, scoreboard, coverage or timeout.
2. Build the smallest reproducible scope: one test, seed, interface, transaction or state transition.
3. Compare expected and observed behavior at the relevant sampling edge, including reset and backpressure.
4. Trace causality backward through the transaction, state machine, queue, arbitration and clock-domain boundaries.
5. State one or more falsifiable root-cause hypotheses and the observation that would distinguish them.
6. Apply the smallest in-scope fix or add the smallest diagnostic instrumentation.
7. Re-run the minimal reproduction first, then the relevant regression slice.

## Required checks

- Check reset release, unknown values, enable/valid/ready timing and off-by-one sampling.
- Check width, signedness, packing, ordering, ID/tag matching, queue full/empty and response ownership.
- Check CDC assumptions, synchronizer latency and whether the waveform is from the current build.
- Separate the first causal error from secondary protocol violations, scoreboard mismatches and timeout fallout.
- For a protocol failure, apply the selected protocol pack and record the exact version/layer assumption.

## Evidence

Report the failing command, source revision, test/seed, first failure timestamp or cycle, relevant artifact paths, minimal reproduction, hypothesis, change and before/after results. Mark unavailable waveforms, logs or checks as skipped or blocked; never infer a passing result from an incomplete trace.

## Boundaries

- Do not treat a waveform screenshot as proof without the associated test and revision.
- Do not modify generated, vendor or read-only files.
- Do not hide a flaky or environment failure behind a functional diagnosis.
- Do not launch an unregistered command, remote job or destructive cleanup through the kit.
