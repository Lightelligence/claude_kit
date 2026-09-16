# Failure classification

Classify using the earliest supported causal evidence, not the loudest final error.
These are analysis categories, not evidence JSON status values.

| Category | Distinguishing evidence |
| --- | --- |
| Environment/license/resource | Launch, license checkout, scheduler/resource or dependency failure before the intended check; not proof of a DUT failure |
| Compile | Source syntax/type/preprocessing/compile-order diagnostic; verify selected sources and configuration |
| Elaboration/link | Hierarchy, parameter, binding, library or DPI resolution; distinguish missing inputs from source defects |
| Runtime/protocol/assertion | Actual accepted transactions and property activation/timing against the applicable requirement |
| Scoreboard | Expected/actual identity, ordering, masking, sampling and reset state; the DUT and checker are both candidates |
| Timeout | Last useful progress, pending work, objections and scheduler/process state; timeout alone does not establish deadlock |
| Coverage | Collected metric, enablement, sampling, reachability and exclusions; a missing metric is neither zero nor full coverage |
| Unknown/incomplete | Ambiguous run identity, absent/truncated artifacts or unfinished execution; do not force a diagnosis |

One run can have secondary symptoms across categories. Report the causal chain
and uncertainty rather than treating every cascade as an independent defect.
