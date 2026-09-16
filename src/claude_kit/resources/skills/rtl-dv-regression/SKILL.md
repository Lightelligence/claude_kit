---
name: rtl-dv-regression
version: 1
description: Plan bounded RTL/DV check sets, compare or triage existing regression results, and execute only engineer-selected runs through the project interface.
---

# RTL/DV Regression

## Select the mode

Planning and existing-result triage are read-only. Neither a new DV test nor a
request to explain failures authorizes a run. Use regression-triager guidance for
selection/analysis; commander is only an explicitly delegated execution role and
must be available before delegation. Otherwise apply guidance in the current session.

Reuse current facts and check choices. Use `plan_task` only for unclear routing,
and `list_catalog(category="checks")` in compact kit MCP mode only when the current
check mapping is needed. Number applicable options with purpose, tool/backend,
target/test/configuration, artifact destination and known cost or unknown estimate.
Separate compile, simulation and regression choices; don't append coverage,
synthesis or CDC automatically. Reuse existing selections without repeated approval.

## Execute only the selected set

Before each run bind source revision/dirty state, working directory, required
target/test/seed, simulator and output/run identity. Clarify missing inputs instead
of guessing. Keep the engineer's order and dependencies. Report blocked/not-run
items individually; continue independent selected checks when safe.

Use registered project MCP tools in MCP-only projects, with no shell fallback.
Use declared wrappers only if project policy permits. A submitted remote job is
not completed; preserve its job ID and inspect its actual status/results before
claiming success. Do not submit duplicates because a client call timed out.

Bound retries and expansion to explicit selections/budgets. New seeds, reruns and
wider slices need authorization unless already covered by that scope. Preserve
original failures; a later pass does not erase flakiness or prove a fix.
Do not delete logs, waveforms, coverage databases or lock files as triage.

## Triage and compare

Read [Result-set triage](references/result-triage.md) for existing regressions or
multiple results. Start with bounded summaries/first meaningful errors, then inspect
one representative per provisional failure group. Locate artifacts by exact run,
not modification time: configured external roots use `discover_regression_artifacts`
and `read_regression_artifact`; checkout-local logs use `read_artifact`.
Keep lock files visible as an in-progress clue, not definitive completion status.

## Report

Return one result per selected check or observed run, aggregate counts with their
denominator, run identity, first causal evidence, failure class, artifact paths
and unresolved gaps. Separate tool exit status from verification outcome and
unknown/in-progress results from failures. For comparisons state what is comparable,
what changed and what cannot be concluded. Propose the smallest next check;
do not execute the proposal automatically.
