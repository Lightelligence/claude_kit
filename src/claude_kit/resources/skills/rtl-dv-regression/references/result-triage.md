# Result-set triage

Use the shared [failure classification](../../rtl-dv-debugging/references/failure-classification.md)
when classifying results. Regression owns selection, run identity and aggregate
comparison; debugging owns deeper causal investigation of a selected failure.

1. Establish the expected run matrix: revision/configuration/target/test/seed,
   requested count, completed jobs and result locations. Separate missing,
   duplicate, cancelled and in-progress records from completed runs.
2. Check command exit, completion markers, expected checker/test results and
   artifacts. Exit zero with absent expected checks is unknown, not a pass.
   A client timeout can leave a remote job running; inspect that job before retry.
3. Group failures provisionally by phase, first meaningful signature and relevant
   configuration. Normalize volatile paths/timestamps without erasing transaction,
   ID or revision distinctions. Similar messages do not prove a common root cause.
4. Inspect one representative per group; retain member run IDs, counts, seeds,
   first-error locations and outliers. Split a group when evidence shows different
   causes. Avoid reading every full log or opening every waveform by default.
5. Compare like-for-like tests/configurations and seed sets; show added/missing
   tests and changed denominators separately. Do not call a new-seed pass a verified
   fix or compare coverage percentages from different metrics/exclusions as equal.
6. Preserve attempts individually. Retry-passed failures remain flaky/investigation
   candidates. Distinguish license/resource/infrastructure interruptions from DUT
   failures without hiding either in aggregate counts.

Return counts with a stated denominator, provisional groups, representative
evidence, unclassified/outlier runs and a bounded proposed next selection.
No rerun, artifact cleanup or coverage merge follows from analysis alone.
