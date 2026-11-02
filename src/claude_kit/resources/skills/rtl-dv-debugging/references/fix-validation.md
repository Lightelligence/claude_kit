# Validate a fix and hunt its variants

Use this after the cause is known and a patch exists, or when explicitly asked
where else the same bug occurs. Ordinary failure triage need not run this flow.

1. Preserve a base input snapshot before patching, then capture patched inputs
   after the edit. Include relevant RTL, TB, spec, configuration and dependency
   locks. Keep logs and records outside those input trees. The CLI is
   `python <kit>/bin/claude-kit dv fix-snapshot --project-root . --input <tree>`;
   repeat `--input` for additional source roots.
2. Reproduce the original failure on base and verify it passes on patched with
   the same test/configuration/seed/tool version. A license error, timeout or
   unrelated failure is not reproduction. License availability is owned by the
   engineer: record the blocker and wait for their resolution, without license
   repair or repeated retries. Retain the specific checker or
   assertion failure signature. Normal control and related regression checks
   should pass on both. Add paired variant checks when genuine variants exist.
3. Start a variant plan with the confirmed root cause, explicit source scope,
   known path/line and an exact literal matching it. Broaden one element per
   pattern. `dv variant-search --plan <plan.json>` returns candidate locations,
   file hashes and search gaps under explicit file/byte/match budgets. Candidates
   include guarded/valid code; review their semantics before calling them bugs.
4. Preserve a triage artifact listing dispositions, reviewer, scope limitations
   and any reproduction evidence. A search with zero matches does not establish
   absence. Mark review pending when the remaining scope is material; a human
   may document why a narrower scope is sufficient. Do not silently treat a
   truncated search as complete.
5. The project collector exports actual run records. Call
   `dv fix-report --plan <fix-plan.json> --run <base.json> --run <patched.json>`
   with the full explicit review set for every declared check. Missing pairs,
   stale inputs, changed artifacts, a wrong failure signature or failed normal
   behavior leave gaps. Preserve failed evidence rather than choosing a passing
   seed to hide it. Highest status is `ready_for_review`, never signoff.

Templates: `dv template fix-plan`, `dv template fix-run`, and
`dv template variant-plan`. The templates are incomplete planning inputs, not
evidence. All execution remains subject to the existing project interface and
the user's selected scope; none of these commands executes EDA.
