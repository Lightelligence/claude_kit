---
name: rtl-dv-debugging
version: 1
description: Debug compile, simulation, assertion, scoreboard, timeout and coverage failures from evidence.
---

# RTL/DV Debugging

Start from the reported symptom and existing evidence. A known, bounded failure
needs a focused investigation; do not create a plan, delegate, or run additional
checks merely because a file, step or query count was reached.

## Establish and trace evidence

Capture the command, cwd, source revision, target, test, seed, simulator and
first meaningful error. Confirm the artifact belongs to that run. Separate
environment, compile, elaboration/link, runtime, protocol, assertion, scoreboard,
coverage and timeout failures; an error cascade is not a list of independent bugs.

Locate the earliest component boundary where observed behavior diverges from
the requirement. Trace the incorrect value or event backward through its
producers, transformations and configuration to the source; the final checker
or error location need not be the cause. Compare a known-good case under
comparable revisions, inputs and environment, expanding only differences that
could explain the symptom. Reduce to a test, seed, transaction, cycle or bounded
observation when that helps distinguish causes.

## Test a hypothesis

Before an expensive or uncertain experiment, identify the hypothesis, the
observation that distinguishes it from alternatives and what would refute it.
Choose the smallest useful experiment and isolate changed variables where
practical. Update the hypothesis from the result; do not stack incompatible,
unconfirmed experimental edits. Reassess repeated attempts that add no evidence
instead of using a fixed retry or query count as an approval gate.

Recover at the failed stage and retain unaffected completed work. Reuse compiled
artifacts only when the existing execution interface verifies source, tool and
configuration compatibility; do not bypass fingerprints, leases or locks. Prefer
existing logs, waves and assertions to new probes. Tag temporary instrumentation,
limit its scope/output and stop condition, and remove it when no longer needed.
Keep full evidence in artifacts and return focused ranges or summaries.

## Fix and verify

Apply the smallest change addressing the supported cause. Rerun the original
reproducer and affected checks only within the engineer's existing selection
and the project's execution interface. Propose an unselected required check;
diagnosing existing evidence does not authorize a new simulation. Preserve
before/after evidence and distinguish missing results, failed queries and
unsupported capabilities from successful checks with no findings. Never turn
a clean exit, empty result or incomplete waveform into a pass.

Report observed facts, the supported cause or remaining hypothesis, evidence
that confirmed or refuted it, the change, actual verification and execution
limitations. Mark an unconfirmed root cause explicitly. Associate the confirmed
case with an existing requirement ID when available.
