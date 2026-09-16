# Assertion and coverage checks

Check whether the affected mechanism distinguishes correct from incorrect behavior.
A declaration is not evidence that the assertion or coverage point executed.

- **Timing:** Check sampling clock, overlapped/non-overlapped implication, offsets,
  `$past` history and DUT scheduling. Trace explicit cycles before reporting an
  off-by-one defect.
- **Enabling/reset:** Check `disable iff`, initialization and enables against the
  intended property. Look for conditions disabling checks during the target failure.
- **Non-vacuity:** Separate implication passes with no antecedent activation from
  checked transactions. Inspect activation/cover evidence; missing evidence alone
  does not prove vacuity. Account for finite-run and strong/weak liveness semantics.
- **Formal assumptions (when present):** Check exclusions of legal failures and
  circular assumptions. Separate environment obligations from DUT guarantees.
  Record supplied proof bounds/configuration; simulation is not an unbounded proof.
- **Sampling:** Check coverage event, `iff`, transaction validity and field update
  timing. Do not count idle/stalled cycles as completed transactions.
- **Meaning:** Map relevant bins/crosses/transitions to requirements and reachable
  scenarios, including specified errors/recovery. Check ignore/illegal bins for
  masked required behavior. Code coverage alone is not functional completeness.
- **Evidence:** Match reports to source/config/test/seed and checker enablement.
  Distinguish stale evidence, absent results and demonstrated failures. Inspect
  waiver rationale/scope without approving waivers or changing exclusions.

Example: zero assertion failures with no demonstrated activation is an evidence
gap, not a verified transfer property. Demonstrated activation and corner scenarios
should not be reported as vacuity merely because that risk appears on a checklist.
