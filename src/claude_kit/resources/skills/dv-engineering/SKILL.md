---
name: dv-engineering
version: 1
description: Plan or implement scoped DV tests, sequences, checkers and environments with explicit scenarios and engineer-selected validation. New tests do not automatically run simulation.
---

# DV Engineering

## Scope and implementation

Distinguish planning, implementation and execution requests. Reuse known context;
use `plan_task` only for unresolved routing. Apply dv-architect/dv-engineer role
guidance as relevant; those names do not imply installed subagents. A plan-only
request does not authorize edits, and an edit does not authorize EDA execution.

Identify the requirement, allowed source paths and existing bench conventions.
Map relevant positive, boundary, negative, reset and recovery scenarios to
stimulus, observation, expected result and a useful failure diagnostic. Do not
add every scenario category to every test. For implementation, read
[DV change checks](references/change-checks.md) for the affected component only.
Preserve user edits and vendor/generated boundaries; modify only the requested
behavior and necessary test/build integration.

Inspect the change statically. Separate intended scenario coverage from observed
coverage: a test or covergroup definition is not proof it ran.

## Engineer-selected checks

Present a numbered menu using the project's current check mapping, reusing choices
already made for this task. For each applicable choice, identify purpose, registered
tool/target/test, required inputs, artifact destination and known cost (or unknown).
Mark quick compile checks separately from simulation, regression, coverage,
synthesis and CDC; do not propose unrelated expensive lanes as routine DV work.
RTL-only lint does not validate DV syntax. A recommended check is not permission.

Execute only the engineer's selected checks in their chosen order. Reuse explicit
approval or explicit delegation to an available commander within its stated scope;
do not repeatedly ask for the same approval. Resolve target, test, simulator, seed
and source identity when needed for execution, not as prerequisites for every edit.
If inputs or prerequisites are missing, block only the affected item and explain
which dependent items cannot run. Do not silently omit selections or add reruns.

Follow the project's execution contract. In MCP-only projects use registered MCP
tools; an unavailable tool is a blocker, not permission to use a shell wrapper.
Declared wrappers are usable only where project policy permits. Before proposing
wider execution, preserve the first causal failure; use rtl-dv-regression guidance
only when selection or result-set triage needs it.

## Handoff

Return changed files and reasons, scenario/checker changes, static findings,
one result per selected check, aggregate counts and remaining blind spots.
Default simulation/regression status is not run. Distinguish DUT, stimulus,
sampling, environment and coverage issues. A run passes only when execution,
expected results and required artifacts support it; registration or exit zero
alone is insufficient. Formal evidence-file preparation is a separate requested
deliverable, not an automatic extra step for every edit.
