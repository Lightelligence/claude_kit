# Shared SoC operating contract

## Normal Claude Code workflow

1. Use only the kit query needed for the task: profile for project facts,
   plan_task for routing, resolve_context for selected context, or inspect_design
   for a root summary. Do not call all four for every edit; reuse current facts.
2. Select only the roles, protocol/VIP packs, and skills relevant to the task.
   Read only task-relevant Bazel rules under .claude/rules/ before editing.
3. Inspect the smallest useful RTL/DV scope, then edit the requested files.
   hw/** is writable and is the normal location for RTL, DV, and PD work.
4. Ask the engineer to select validation checks. Record results, run IDs,
   artifact paths, skipped checks, and unresolved risks in evidence.

The repo-local Python CLI is a maintenance and diagnosis fallback. During a
normal Claude Code session, use the registered claude-kit MCP tools instead of
asking the engineer to run Python commands manually.

## Context economy

Use `.claude/scripts/loop_prompt_budget.py --check` to check loading budgets; see `.claude/references/log-evidence.md` for kit adapter defaults.

Do not read large files whole. This repo contains very large artifacts
(disassembly/verilog dumps, regression logs, detailed style standards).
Priority order for any lookup:

1. Follow root CLAUDE.md: enable `soc-lsp` and use its symbol/definition/reference
   tools first. If the file is unknown, discover candidate paths with scoped `rg`,
   then return to LSP. Read only the resulting ranges (`Read` with offset/limit).
   Use text search for literal keywords and unsupported or incomplete LSP results.
2. Only when comprehension spans many files or one huge file and no verbatim
   text is needed for an upcoming edit, delegate to a subagent — and instruct
   the subagent to search-and-slice too, never dump whole files.

## EDA execution invariant

EDA execution is MCP-only. Use the registered tool server and the task facts
it requires:

- soc-build-bazel — Bazel filelists, lint, compile, single simulation,
  regression, coverage, synthesis, and CDC.
- soc-integrate-bazel — WORKSPACE, BUILD, dependency, and vendor-IP checks.
- xverif — registered verification debug and coverage actions. For xdebug,
  call xverif_tools once, then xverif_debug_get_schema for the selected action,
  and use the managed session/query lifecycle. Do not guess actions or silently
  change backend, transport, or data source.
- The registered silicon-crew generators and soc-openroad server for their
  declared responsibilities.

Do not call bazel, vcs, verilator, xcelium, dc_shell, yosys, or CDC tools
directly for an EDA operation. Read-only Git and file inspection are not EDA
execution, but the project MCP contract still takes precedence over ad-hoc
build commands.

The xverif xdebug action catalog and vendor-backed queries use the VCS/Verdi
environment loaded by the registered simulation/simmer flow. Do not require
the engineer to set VERDI_HOME or VCS_HOME in the ordinary Claude Code shell.
When an xdebug action needs that environment, start or reload the xverif MCP
server from the same approved simulation environment. A separate simmer
process cannot update the environment of an already-running MCP child.
Keep site paths, license values, and credentials outside the repository.

## Regression artifact lookup

The project profile's [artifacts.regression] section identifies the matching
regression root for this checkout. Use the claude-kit MCP tools
discover_regression_artifacts to select logs, then summarize_regression_log and
read_regression_log_range for bounded evidence. See
.claude/references/log-evidence.md when investigating logs. The root is derived from the current checkout name;
do not scan the parent regression directory or choose a latest run by mtime.
When multiple runs match, require the engineer to select a target/test/run.

## DV check menu

For a DV environment or test change, first show the engineer a proposed list.
The default lightweight checks are:

- soc_flist — query dependencies; its bounded output is not a generated filelist.
- soc_lint — VCS-only RTL lint for an affected RTL module; it does not check DV files.
- soc_comp — DV bench/test compile-only validation (`--no-run`), including DV syntax.

The following checks are explicit engineer choices and must not run
automatically after creating or editing a DV test:

- soc_sim — run one selected test.
- soc_unit_test — run one concrete `//hw/rtl/...:<target>` RTL unit-test target
  with an explicitly selected `vcs` or `xcelium` simulator.
- soc_regress — run a selected regression matrix.
- soc_coverage — collect coverage.
- soc_syn — run synthesis.
- soc_cdc — run CDC analysis.

If the engineer selects multiple checks, display the complete selection first,
execute every selected item through its registered MCP tool, and return a
per-check report containing status, server/tool, target or test facts, run ID,
artifact/report paths, and failure context. A new DV test or an RTL edit does
not imply a simulation or RTL unit-test request. `soc_unit_test` is targeted
execution and does not replace `soc_lint`, DV compile-only `soc_comp`, or DV
`soc_sim` evidence.

This check-selection policy also governs subagents, recovery, and all delivery
modes. A stale stage, risk escalation or proposed plan is not execution approval.
Reuse explicit selections already made for the task. If a required check is not
selected or its evidence is incompatible with the state validator, leave the
stage open and report `needs-validation`; never manufacture closure evidence.

Never invent a target or test alias. Ask for the real module, top, test
selector, simulator, seed, and other required facts when the task does not
provide them. Keep resolve_target() and resolve_test() pass-through unless the
project deliberately introduces a reviewed, reusable mapping.

## Editing and safety boundaries

- Read the relevant target rule and existing local conventions before edits.
- Keep generated logs, waveforms, coverage, and reports under the profile's
  out/ artifact directories; do not commit caches or tool databases.
- Do not edit the kit submodule contents in place; update its pin only as an
  explicit dependency change.
- Preserve .mcp.json server names and project-owned definitions when adding or
  updating the claude-kit bridge.
- Do not claim validation success without the corresponding MCP evidence.
- Follow root CLAUDE.md delivery: reuse the designated branch/MR, or create a feature branch; verify, commit and push.
  No repeated publication approval; explicit local-only requests override. Never merge.

## Useful prompts

~~~
Plan a DV change for <module/test>. Inspect the target rules and show the
check menu, but do not run simulation yet.
~~~

~~~
I select soc_flist, soc_lint, and soc_comp for target <target>. Execute them
through the registered MCP tools and return one report per check.
~~~

~~~
I select soc_sim for test <test> with simulator <simulator> and seed <seed>.
Run only that selected MCP check and record the evidence.
~~~
