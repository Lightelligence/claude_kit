---
paths:
  - "hw/**"
---

# Project development workflow (Bazel)

The **DV check menu** in `.claude/CLAUDE.md` is the authority for check
selection. A delivery mode, risk escalation, stale stage, or available test is
not execution authorization. Reuse an explicit selection already made for the
task; otherwise present the proposed checks before running EDA.

## Roles and validation

| Owner | Work | Proposed checks (not automatic execution) |
|---|---|---|
| `soc-rtl-designer` | `hw/rtl/<module>/` sources | `soc_lint` for RTL; `soc_flist` for dependencies; selected `soc_unit_test` only with a concrete RTL unit-test target and simulator; `soc_comp` only with a real DV bench selector |
| `soc-integrator` | BUILD, WORKSPACE, vendor-IP mappings | Relevant `soc-integrate-bazel` checks; selected RTL lint or DV compile |
| `soc-verification-engineer` | `hw/dv/` environments and tests | `soc_flist` and compile-only `soc_comp`; RTL-only `soc_lint` is not a DV syntax check |
| `soc-synthesis-engineer` | `hw/pd/` constraints and synthesis setup | `soc_syn` only when explicitly selected; real STA reports for timing claims |
| `soc-reviewer` | Read-only review | Inspect supplied evidence; report missing validation without launching it |

Discover the actual module, bench, test and target from the task and BUILD
definitions. Do not assume one chip top or test applies to every change.
Use the names and schemas in `22_toolchain_bazel.md` and the registered tools.
`soc_comp(module_dir="sys", test="<actual_test>")` compiles that DV bench;
passing an RTL module name does not make it an RTL compile tool.
`soc_unit_test(target="//hw/rtl/<package>:<target>", simulator="vcs")`
executes an RTL unit test after checking its Bazel rule metadata; it is not a
generic Bazel test runner or pipeline-closure substitute.

## Development and delivery

1. Inspect the requested scope and relevant rules, then implement the change
   within the role's write scope. Route BUILD changes to the integrator and
   RTL changes to the RTL owner.
2. Present relevant checks using the project check menu. Creating or editing
   a test does not select `soc_sim` or `soc_unit_test`. Regression, coverage,
   synthesis and CDC remain separate choices, not mandatory follow-up work.
3. If multiple checks are selected, show the complete selection and execute
   every selected item through its registered MCP tool. Report each result;
   if a dependency blocks an item, report it as blocked, not passed.
4. Record status, server/tool, target/test/seed, run ID and actual artifact
   paths where returned. Missing evidence is a limitation, never invented data.

`dev` keeps stages open. `merge` and `signoff` identify required evidence and
review depth; neither automatically starts RTL unit tests, simulation,
regression, coverage, synthesis, CDC or physical design. If required evidence
is missing and its check is not selected, leave the stage open and report
`needs-validation`.
An approved simulation already includes compilation; avoid a redundant compile
unless separately selected for a concrete reason.

## Pipeline state

Use the state CLI described in `25_pipeline_state_bazel.md`, not handwritten
JSON. Initialize only missing state and mark a stage in progress before its
work. Close a stage only when the state validator accepts current, real
evidence. A source edit or a selected check alone is not proof of completion.
Do not claim signoff or merge merely because development checks passed.
