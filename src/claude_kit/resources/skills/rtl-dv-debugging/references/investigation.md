# Failure investigation

Use [failure classification](failure-classification.md) for initial triage; then
inspect only relevant code/log regions and the requirement governing the symptom.

- **Compile/elaboration:** Find the earliest actionable diagnostic and actual build
  sources, defines, include/package order, libraries and parameters. Later unknown
  symbols may be fallout. Do not invent stubs or remove checks to obtain a pass.
- **Protocol/scoreboard:** Establish clock/reset, acceptance event, expected versus
  observed transaction, IDs/order and comparison time. Check monitor sampling and
  object lifetime as well as DUT behavior. Trace the causal chain backward.
- **Waveforms:** Confirm database/build/run identity, time units and dump window.
  Query a narrow signal set around the first failure. Missing/optimized signals,
  X/Z, incomplete dumps and different sampling edges limit conclusions. Read
  action schemas only for needed operations and use task-owned managed sessions.
- **Timeout:** Determine whether the job/process is still active and locate last
  progress, outstanding transactions, objections and dependencies. Distinguish slow
  execution, stalled infrastructure, incomplete logs and functional lack of progress.
- **Assertion/coverage:** Check activation, sampling, reset gating, relevant metric
  collection and reachability. No assertion failures is not proof of activation;
  empty coverage output is not proof of zero coverage. Do not change exclusions.
- **Hypotheses:** State expected behavior, observed evidence, candidate mechanism
  and one discriminating observation. Mark inferred internal values as unknown
  until supported; a plausible source pattern is not a measured waveform value.
- **Fix and verification:** Only when fixing is requested, make a bounded change
  respecting project permissions and preserve before/after identity. A confirming
  run is separate selected execution. Keep a proposed reproducer distinct from
  one that actually ran, and preserve unsuccessful attempts.

Static analysis can establish a source defect when its preconditions and outcome
are demonstrated. Dynamic probing is useful for uncertainty, not an automatic
requirement or implicit permission to instrument/rebuild the testbench.
