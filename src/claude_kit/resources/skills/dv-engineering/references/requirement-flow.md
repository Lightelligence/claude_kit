# Requirement and coverage loop

Use one existing requirement ID as the unit of work. Keep the project's
testplan authoritative. If it already uses Hjson/CSV, let its thin adapter
export the kit DV plan; do not hand-maintain a second requirement table.

Before editing, bind spec reference, configurations, existing sequence API,
checker IDs, coverage targets and unresolved semantics. A test name is not a
checker. Expected behavior comes from the approved spec, not an RTL copy.

## Scenario card

Fill only the fields needed for this task; save alongside the project testplan
when an auditable work item is useful.

```text
Requirement / spec reference / configurations:
Goal and explicit non-goals:
Unresolved behavior (e.g. reset and completion on the same edge):
Existing base sequence and supported API calls:
Setup -> stimulus steps -> observation -> expected result:
Checker IDs and how to demonstrate activity:
Coverage target IDs and sampling point:
Known-bad transaction / negative control for critical checkers:
Input baseline / command / test / seed / output location:
Budget: compile attempts, target runs, wall time, concurrency:
Stop condition and next useful experiment:
```

This adopts HAVEN's separation of scenario intent from stable UVM structure.
Reuse project drivers, monitors, reference models and sequence templates.
Do not add a protocol DSL or regenerate the environment just to add one case.
Unknown APIs or invalid constraints are gaps to resolve, not inputs to silently
drop. Template-generated code still needs compilation and behavioral checks.

## Execute within the existing authorized budget

1. For a coverage hole, distinguish absent stimulus, illegal/overconstrained
   stimulus, sampling error, DUT failure, configuration mismatch and possible
   unreachability. Query exact target IDs with the installed xverif schema;
   preserve incomplete/truncated results.
2. Make the smallest sequence/checker change. Use the selected project runner.
   Suggested starting budget: two compile repairs, three target runs, one job
   at a time. Project limits and existing user authorization take precedence.
3. Capture `dv snapshot` after edits and before submission. The adapter must
   bind it to the files actually compiled, including dirty inputs. For remote
   jobs, hash the staged source; do not attach today's digest to an old run.
4. Verify the target was reached AND the checker was active and successful.
   A process exit code or coverage percentage alone does not establish either.
   Use a controlled negative test for critical checkers; retain its result.
5. Export normalized run JSON from the existing result collector. Include all
   selected seeds/configurations, including failures and incomplete jobs.
   Keep run state in the runner; `dv report` is a read-only evidence join.
6. Run `<kit>/bin/claude-kit dv report --project-root <project> --plan
   <plan.json> --run <run.json>` with the project's Python >=3.11. Repeat
   `--run` for the full review set. Report readiness, gaps and remaining risk.

Stop or change hypothesis when the budget is used or repeated calls provide
no new evidence. Never weaken a checker, strengthen an assume, or add an
exclusion merely to obtain a green result. Surface the requirement decision
and continue independent work within scope.

## Formal evidence

Keep property set, scope, clock/reset, assumptions and their review evidence.
Record actual proof status, cover/antecedent reachability and vacuity checks.
Bounded success, timeout and inconclusive are gaps for unbounded closure.
The kit checks declared evidence, not the soundness of the formal model.

## Readiness is not signoff

`dv report` checks each requirement × configuration × case. It invalidates
evidence after declared input or plan changes and checks artifact hashes.
It does not discover omitted requirements or omitted runs, resolve spec
ambiguities, prove checker semantics, approve waivers or accept residual risk.
Human review still owns those decisions. Pin the kit revision in the parent
project; keep every plan, scenario and execution artifact in that project.
