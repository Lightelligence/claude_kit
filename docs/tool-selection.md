# Choosing Claude Code tools for RTL and DV

This guide is for engineers working in a project attached to claude_kit.
The project's `.mcp.json` and Claude settings determine which servers are
available. A bundled skill or a Python source file does not enable a server.

## Coverage queries versus coverage generation

`soc_coverage` belongs to the project build/coverage flow; `xverif_cov_*` reads
an existing VDB. An FSDB alone is not a coverage database. Supply an explicit
VDB path, inspect the selected action schema, and open a task-owned coverage
session. Do not enumerate every action for a focused question.
Summary/query uses URG; exclusion operations additionally require Verdi Python
NPI. Successful summaries do not prove exclusion support, and listing actions
does not prove VDB access.

| Question | Selected action | Interpretation |
| --- | --- | --- |
| Which RTL lines or branches were exercised? | `code_coverage.summary` | Requires those code metrics to have been collected. |
| Which covergroups/coverpoints were exercised? | `functional_coverage.summary` | Functional coverage can exist without RTL code coverage. |
| What happened to assertions and cover properties? | `assert.summary` | Assertion results are not a substitute for code or functional coverage. |

An empty line/branch result means no matching data was returned, not 0% or
100% coverage. A VDB containing only functional coverage may legitimately lack
URG's module/assertion report files. If the installed server rejects it, report
the error and version; do not fabricate missing files or start a simulation.
Functional scores can use coverpoint/cross averaging rather than the simple
ratio of the displayed counts. Preserve the tool's score and explain its basis.

```text
Use the debug tool profile to inspect the existing VDB at <absolute-vdb-path>.
Query code_coverage.summary for line and branch only. Report coverage gaps and
the database identity. Do not run simulation, change exclusions, or export a
full report. Close only the coverage session opened for this task.
```

For a DV functional-coverage question:

```text
Inspect <absolute-vdb-path> with functional_coverage.summary, grouped by
covergroup. Show the lowest-scoring groups and explain the score basis.
Report unavailable metrics explicitly; do not interpret missing RTL metrics
as zero coverage. Reuse this task's session, then close it. Do not simulate
or modify exclusions.
```

For detailed gaps, narrow the instances and metrics first. Batch related
instances into one export to avoid repeated URG runs. Prefer compact output;
choose JSON for programmatic consumption. Exclusions require an engineering
decision, not automatic score improvement. Persist reasons before closing a
dirty session; do not discard them or clean other tasks' sessions casually.

## Start with the task, not the complete tool catalog

Project checks may declare `applies_to = ["rtl"]`, `["dv"]`, `["rtl", "dv"]`,
or `["all"]`. Task plans do not recommend checks outside the workflow scope.
Unscoped lint is optional in DV plans until its DV source coverage is confirmed.
Checks remain selectable and simulation confirmation requirements are unchanged.
This describes source applicability, not filesystem or execution permissions.

| Your task | Start here | Do not confuse it with |
| --- | --- | --- |
| Understand a module or plan a change | Kit project profile/context and the relevant RTL/DV skill | A build or a verification result |
| Find a symbol, definition or reference | The project's language-server MCP | Compiler validation; an empty search is not proof a symbol does not exist |
| Check synthesizable RTL | The project's RTL-only lint tool | DV testbench compilation |
| Validate a DV edit without running a test | The project's compile/elaboration tool | Simulation; compile PASS says nothing about runtime checkers |
| Run a selected test | The project's simulation tool | A regression or coverage signoff; avoid a redundant compile if the tool already compiles |
| Investigate an existing failure | Bounded log discovery/read, then debug tools as needed | Automatically starting a new simulation |
| Inspect existing waveform/design data | xverif debug catalog, action schema, managed session/query | Producing new FSDB/design databases |
| Inspect existing coverage data | xverif coverage catalog/schema/session/query | The build server's coverage execution command |
| Calculate bit fields or explain SVA | xverif bit or SVA tools | Guessing the result in prose or attempting a waveform session |
| Assemble descriptor/header fields from known byte fragments | xentry decode with a field-layout config | Waveform extraction, valid/ready detection or protocol interpretation; obtain the accepted fragments first |
| Generate register RTL/RAL or CRG | The enabled register/CRG generator | Hand-editing generated output |
| Perform synthesis, CDC or physical design | The explicitly selected project lane | Routine work automatically required after a DV change |
| Prepare a delivery | Evidence review and the project's delivery workflow | An ordinary development iteration or automatic signoff |

In a Bazel project, prefer its registered Bazel adapter. A generic Make-based
server with a similarly named `soc_comp` is not an interchangeable backend.

### Optional Make project tools

Use `soc_init` only in a new standalone project directory. `soc_add_chip` adds a
chip module; `soc_add_ip` adds a digital or third-party IP. These scaffold files,
not completed or verified designs. Do not apply this layout to a Bazel checkout.

`soc_flist(path, output, recursive)` selects HDL source paths, not a dependency
ordering or a syntax check. With the kit's reviewed filelist adaptation,
`recursive=false` scans only the selected directory and `true` includes children.
An omitted MCP output returns the list as text without writing `filelist.f`;
an explicit output writes the requested file. The maintenance CLI keeps its
existing default file output. Older unadapted servers violate the false/omitted
argument contracts: use explicit output paths and update before relying on them.

```text
Use the optional Make soc-build server to create <new-project> under <owned-dir>.
Add a digital IP named <ip>. Generate its RTL filelist with an explicit output
path. Compile the selected module with VCS and the specified top <top>.
Do not simulate, collect coverage, run regression, synthesize, or run CDC.
```

Registered Make/VCS compilation of a generated parameterized RTL wrapper passed
on ETX (`34806397148`). This is compile/elaboration evidence, not simulation or
acceptance of every backend. After applying kit `6848cbd`, all ten actual MCP
cases pass (`34806987896`), including shallow/recursive selection and text-only
output, plus 38 mocked-EDA unit tests and ten project-contract checks. The real
compile was repeated successfully; no simulation was run.

### Register generation versus CRG generation

`yml2reg` generates standalone APB/AHB/DAB register RTL from YAML. All three
protocol outputs from the shipped `demo_docs.yml` pass registered VCS compilation
and elaboration (`34807660541`); this is not bus-transaction simulation evidence.
UVM `.svh` outputs need a UVM package/library and a compile harness, not just an
RTL filelist. A missing `uvm_pkg` is a compile-environment prerequisite, not proof
that the generated RAL is malformed.

`crg-req-to-design` turns requirements into design collateral;
`crg-gen` turns the reviewed design Excel into clock/reset RTL, a top and its
register bank. The top still needs the project's actual clock/reset primitives.
Do not invent empty cells to make elaboration pass. The old embedded CRG register
implementation silently omitted interrupt banks and write-protection information.
The reviewed adaptation now delegates to the sibling `yml2reg` implementation,
with CRG-specific `register_field` naming, rather than maintaining two RTL engines.
Install both skills from the same kit export; no additional MCP server is started
by this reuse. Standalone `yml2reg` keeps its original naming and three protocols.
CRG remains APB-only until its other top-level bus contracts are validated; AHB/DAB
fail explicitly. The parent also aligns CSV module/bus ports while preserving SDC
instance paths, and propagates child errors to MCP. Apply the parent/helper
adaptations together; the shared-backend ETX acceptance is still pending.

```text
Use the reviewed CRG Excel <input> to generate into <owned-output-dir>.
Check register/top port consistency and identify the required clock/reset cells.
Compile through the registered project adapter only if those real dependencies
are available. Report missing cells explicitly; do not substitute stubs or simulate.
```

### RTL integration is not build integration

`soc-integrate` reads module interfaces and generates RTL; `soc-integrate-bazel`
manages build/dependency facts. Choose the operation you need:

| RTL integration tool | Use |
| --- | --- |
| `soc_extract` / `soc_csv` | Inspect ports in text / export a review table |
| `soc_instantiate` / `soc_wrap` | Generate an instance snippet / a pass-through module |
| `soc_integrate` | Generate a top, review CSV and `.integrate.json` using selected module files and a reviewed port map |
| `soc_extract_map` | Inspect existing top connections; optionally verify against module sources |
| `soc_snapshot` / `soc_diff` | Save an interface baseline / compare against it |
| `soc_update` / `soc_remove` | Refresh the owned generated top / remove a selected module and its connection records |

These operations are not a mandatory sequence. Use explicit output paths:
CSV/snapshot defaults can write files beside inputs or in the server's working
directory. Generation is not compilation, CDC validation or protocol verification.
The lightweight parser is not a complete SystemVerilog frontend. Unsupported
types and arrays must fail explicitly; normalize them in an approved wrapper,
not by dropping dimensions or renaming a type token into a port.

```text
Use soc_extract on <module-file> to inspect its complete interface.
Do not generate or overwrite files. If a declaration is unsupported, report
the limitation rather than returning a partial port list.
```

```text
Use soc_integrate with module_files=<selected-files>, top_name=<top-name>,
output_file=<owned-output-file>, and port_map=<reviewed-map.json>.
Review the generated connections and config. Do not compile or simulate.
```

For entry decoding, use `xverif_entry_explain` to inspect an unfamiliar layout,
`xverif_entry_validate` when checking only input/config validity, and
`xverif_entry_decode` when you need field values. Do not automatically call all
three for every decode. The decoder assembles selected bits and returns raw
fields with provenance; it does not infer handshake acceptance or enum meaning.

```text
Use xverif_entry_decode with config_path=<layout.yaml>, input_path=<beats.jsonl>,
and output_format="json". Report the requested fields, their raw values and
source fragments. Do not open a waveform session or infer protocol semantics.
```

## What each layer does

### Library stubs versus real timing libraries

`lib-db-gen` is a **skill-owned helper, not a registered MCP server**, in the
audited consumer. Its deployed helper uses LC, while the newer bundled server
also advertises DC options; do not copy that server over the older helper or
silently change compiler backends. The project's MCP-only EDA contract still
applies: a library skill does not authorize direct `lc_shell` execution.

The documented `--no-run` preparation emits Liberty/Tcl without executing a
compiler. It does not create or validate a `.db`. Keep all output/work paths
explicit and task-owned. Use `convert` for a real Liberty input, and `stub` only
for early black-box bring-up. A zero-area stub is not a standard-cell target
library or timing/power evidence. Symbolic widths still produce an explicit
scalar warning in this helper; provide a width-resolved wrapper when interface
fidelity matters, rather than treating that approximation as a verified bus.

```text
Use the lib-db-gen skill for preparation only. From <resolved-wrapper.v>, emit
stub Liberty and conversion Tcl under <owned-output-dir> using --no-run.
Check port names, directions and bus widths. Report warnings explicitly.
Do not run LC/DC or claim that a compiled DB or timing library was produced.
```

Live conversion requires a compatible registered execution entry and the
selected compiler/license environment. Neither the missing registration nor a
missing `lc_shell` on PATH is fixed by choosing a different skill.

### Compact kit catalogs

The kit bridge accepts `mcp serve --tool-profile compact`. This advertises
nine read-only tools instead of fourteen, merging six catalog tools into
`list_catalog(category)`, where category is `roles`, `packs`, `providers`,
`skills`, `workflows`, or `checks`. The default `full` profile and historical
catalog calls remain compatible. Execution still requires the separate
`--allow-exec` option and its existing confirmation gates.

For example, ask Claude: `Call claude-kit.list_catalog with category="checks"
and show my validation choices without running them.` A project launcher must
select compact mode before this name appears in its advertised tool list.

The measured compact catalog is 2,523 UTF-8 bytes versus 3,118 bytes for full
(19.1% smaller), using compact JSON serialization of tools/list. This measures
schema size, not total session tokens or business quality; actual project/model
acceptance is a separate check.

- **MCP tools** execute a defined operation with a parameter schema. Keep read,
  generation and expensive verification operations distinguishable.
- **Skills** explain when and how to use a capability. Read only the selected
  skill and the references needed for the current task.
- **Agents/roles** assign bounded ownership. A kit role catalog entry is not
  automatically a registered Claude subagent or a newly available tool.
- **Project rules** hold stable constraints. Runtime settings and tool lists
  belong in configuration, not duplicated across every skill.
- **Maintenance scripts** synchronize or validate configuration. Engineers
  normally use Claude's MCP tools instead of manually invoking those scripts.

A skill name is guidance, not a shell command or an MCP function. In Claude
Code, describe the task and name the relevant skill; Claude uses its built-in
file tools and the selected MCP operations as needed. There is no mandatory
sequence of catalog/profile/context calls for every edit. For example:

```text
Use rtl-design guidance to review <rtl-file> for <specific-concern>.
Read only missing project context. Do not compile or simulate.
```

If Claude cannot find that skill, ask it to inspect the kit's `skills` catalog
and resolve the selected guidance. A catalog entry alone does not mean a native
Claude slash command or subagent has been installed.

`rtl-dv-kit` is the thin project entrypoint; `rtl-dv-context` is for missing or
stale facts and unclear workflow selection. Keep both names compatible, but do
not run both as a fixed pre-edit checklist. Minimal installations may contain
only the entrypoint. Revalidate changed configuration and resolve permission
errors before affected actions; reusing context does not waive those checks.

## Effective RTL prompts

Replace angle-bracket placeholders with your actual task facts.

```text
Inspect <module> and implement <approved-change> using the rtl-design skill.
Preserve its interface and existing unrelated changes. Explain any required
interface decision before changing it. Propose the smallest relevant checks;
do not run simulation, synthesis, or CDC automatically.
```

```text
Use the project's registered RTL lint tool for <module> only.
Report its actual result and artifact path. Do not treat this as DV validation.
```

## Effective DV prompts

```text
Use dv-engineering to add <scenario> to <testbench>.
Reuse the existing sequence, scoreboard, and configuration conventions.
Do not run simulation. After editing, show the available validation choices
and wait for my selection. Distinguish compile-only from runtime checks.
```

```text
Compile and elaborate <testbench> through the registered project MCP tool.
Do not run simulation, regression, coverage, synthesis, or CDC.
Report the result, run ID, and compile log location.
```

```text
Investigate <test> using existing run <run-id>. Read the relevant failure
window, not the entire log. Use waveform queries only if the logs cannot
resolve the question. Do not choose a different run or rerun the test silently.
```

## xverif: discover only what you need

For debug, use `xverif_tools` to obtain the action guide, then
`xverif_debug_get_schema` for the selected action. Open a managed session only
when that action variant requires a database; close your own session when done.
Coverage uses the separate `xverif_cov_*` catalog and lifecycle. Keep action
parameters in the exact schema location rather than copying parameters from
another action with a similar name.

```text
Call xverif_bit_slice with value="32'hdeadbeef", msb=15, lsb=8,
and output_format="json". Report the actual result.
```

```text
Call xverif_tool_help with name="xverif_cov_query" and explain the
inputs needed to inspect my existing VDB. Do not run coverage collection.
```

The xdebug action count is not the MCP tool count. A returned catalog proves
discovery, not successful execution of every action or availability of licenses.

New `init` contracts use on-demand MCP guidance, consistent with the skills:
known-context edits do not require a planning/discovery chain. Existing custom
`.claude/CLAUDE.md` files are preserved by default. Compare and adapt their
relevant instructions; do not run `init --force` simply to obtain the new wording.

## Reduce context without reducing correctness

1. Keep only task-relevant servers enabled by default. Put optional generators,
   physical design and issue-tracker integrations behind an explicit project
   selection, with their dependencies documented.
2. Merge truly equivalent catalog/read operations, not unrelated actions with
   different authorization or parameter contracts. Preserve compatibility when
   removing an old advertised name.
3. Keep skill discovery descriptions concise. Put detailed examples and
   conditional procedures in references rather than always-loaded rules.
4. Use precise module, target, test and run identifiers. Bound log reads and
   query results. Ask for a result summary and artifact path, not full logs.
5. Reuse evidence only when it matches the current inputs and source revision.
   Fewer commands are not an improvement if they reuse stale results.
6. Measure before and after using representative RTL and DV tasks. Schema byte
   size, tool count, latency and actual model token usage are different metrics.

Claude Code supports deferred MCP discovery through Tool Search, but proxy and
model compatibility matter. A custom API gateway may load tools upfront;
forcing `ENABLE_TOOL_SEARCH=true` can fail if it cannot handle `tool_reference`.
Verify the actual configured model and gateway before changing this setting.
See [Claude Code's MCP documentation](https://code.claude.com/docs/en/mcp#configure-tool-search).

## Select a session's MCP servers

In the tested xin_1 integration, ordinary terminal startup is now sufficient:

```bash
claude
```

Its project default contains kit, Bazel build and LSP: 3 servers / 23 advertised
MCP tools, verified with native Claude Code 2.1.267. Optional server definitions
remain in the separate catalog. For waveform/coverage/bit work, start a debug
profile instead; its two servers advertise 45 tools. These are tool counts,
not measured model-token savings. The full task objective still requires the
remaining capability checks listed below.

Run the launcher commands below in your terminal, **not as Claude prompts**.
Inside Claude, describe your task normally and inspect `/mcp` if needed.

Projects can define `.claude/tool-profiles.json` alongside `.mcp.json`:

```json
{"schema_version":1,"profiles":{"rtl":{"description":"RTL editing and checks","servers":["soc-build-bazel","soc-lsp","claude-kit"]}}}
```

Server names must exactly match keys in the selected configuration source:
the catalog specified by `mcp_config`, or `.mcp.json` when that field is absent. Add separate debug,
register-generation or physical-design profiles as needed; the kit does not
invent project-specific server names or change their configuration.

```sh
python3 third_party/claude_kit/bin/claude-kit tool-profiles --project-root .
python3 third_party/claude_kit/bin/claude-kit session --project-root . --tools rtl
```

For a project with a debug profile, start xverif work from the terminal with:

```sh
python3 third_party/claude_kit/bin/claude-kit session --project-root . --tools debug
```

A profile launch starts a new Claude process; it does not dynamically add tools
to an already-open plain session. If a server is missing, check the full catalog
and profile name first; do not clear local disabled-server settings to troubleshoot.

The session command opens native Claude Code. Enter normal prompts there; no
Python command is needed for each MCP call. Optional native arguments follow `--`.
The launcher uses a temporary strict MCP config, removes it after exit, and does
not override models or permission settings. The catalog prints names and
descriptions, not server credentials. Existing disabled-server and organization
policies can still affect availability; check `/mcp` inside the session.

This launcher passed native ETX Claude Code 2.1.267 acceptance with the debug
profile after correcting inherited PROJ_DIR handling in the repo-local launcher.
Only kit and xverif connected. The run took 12.53 seconds, advertised 45 tools,
and verified the absolute xin_1 root through inspect_design, a passed profile
validation and bit result 17. Checkout status remained unchanged. This proves
the tested debug profile's routing and calls, not every capability or token cost.

## Script placement

Projects may keep the complete server definitions in `.claude/mcp-catalog.json`
and set `"mcp_config": ".claude/mcp-catalog.json"` at the top level of
`.claude/tool-profiles.json`. Profile sessions then use that catalog rather
than `.mcp.json`; the path must remain inside the project. Without this optional
field, existing projects continue to use `.mcp.json`. This alone does not change
default startup: the project's config generator must also emit its selected
default subset into `.mcp.json`. Preserve local disabled-server settings.

| Kind | Canonical location |
| --- | --- |
| Reusable kit implementation | `src/claude_kit/` with tests and a documented CLI/MCP entry |
| Project-specific Claude configuration and state helpers | Project `.claude/scripts/` |
| A helper owned by one reusable skill | That skill's `scripts/` |
| General build, regression or release tooling used without Claude | Existing project tooling directory |
| Existing callers that cannot migrate together | A small compatibility launcher, not a second implementation |

Moving a script requires updating root discovery, imports, subprocess callers,
generated launcher templates, tests and documentation. A directory move alone
is not complete. Do not move general build tools just because a Claude skill
also calls them.

The audited consumer has migrated seven Claude helpers (agent profiles, Loop
contracts/state entrypoints, MCP config/runtime/lock sync and prompt budgets).
Old paths are compatibility launchers, not extra MCP tools or startup context.
Loop init/query/update/migrate share `loop_state_core.py`. Its two same-sized
repository-hygiene files are a canonical source and generated copy, not duplicate
Claude tools. Check callers, ownership and generation rules before deleting them.

## What verification reports must say

Record the tested revision, interpreter/tool version, backend/host, exact
operation, expected result, observed result, and artifact path. Distinguish:

- static/schema checks;
- MCP initialize and tools/list;
- a real business call with an asserted result;
- actual Claude selection and invocation;
- untested operations or unavailable external prerequisites.

Do not label mocked unit tests, an empty success envelope, a tool catalog, or
missing-license skips as end-to-end business PASS. Use disposable fixtures for
mutations; never test deletion or publication on unrelated live project data.

### ETX verification scope (updated 2026-09-14)

This is an integration snapshot, not a promise that every backend operation has
passed. The baseline discovered 218 tools across 16 stdio servers, including
disabled optional servers. The eight active stdio servers advertised 89 tools
and 63,682 compact-JSON UTF-8 schema bytes; the HTTP drawing server is excluded.
Those are historical baseline counts. The current default contains only three
servers (`claude-kit`, `soc-build-bazel`, `soc-lsp`) and 23 tools; optional servers
are selected through task profiles. Do not interpret bytes as model tokens.

| Capability | Actual evidence | Remaining acceptance |
| --- | --- | --- |
| Kit compact catalogs | Local compatibility tests; actual ETX catalog is 9 tools / 2,523 schema bytes; native Claude calls succeed | Broader task quality checks |
| Task profiles/session launcher | Local tests; seven profiles parsed on ETX; native debug connects two servers; native RTL/DV each connect three servers and advertise 23 tools, with correct root and read-only calls | Actual implementation quality and unrestricted tool-selection behavior; RTL answer incorrectly generalized “no elaboration” for lint |
| Register generation | All 13 yml2reg MCP entrypoints generated nonempty outputs; XML/JSON/XLSX parsing where applicable | Generated HDL compilation and project-specific semantic checks |
| Bit conversion/slice/eval/check | Real MCP values 255/-1, 190 and 17; true/false conditions, JSON file bindings and conflicting-source rejection verified | Shared MCP still advertises an invalid hex-expression example and misleading values description; [source fix](https://github.com/Lightelligence/xverif/pull/3) is under review. Follow the xbit skill's tested examples |
| SVA list/scan/parse/explain | Four real MCP responses against an owned property fixture | Broader temporal-semantic cases |
| xdebug waveform queries | Registered MCP guide/schema, session open, roots, two batched value queries (10 samples) matched fresh independent converter references; absent signal explicit, owned session closed, input/project unchanged | Complete FSDB/design/action matrix; native NPI coverage remains a separate failing path |
| Coverage reports | Action discovery passes; an isolated parser candidate passed real MCP functional-only VDB open/query/close with cold and warm caches | Parser fix is not deployed to the shared installation; native NPI database open crashes, so exclusion/export acceptance remains failed or unverified |
| Language navigation | Eight real MCP file-navigation calls pass across two workspaces; actual catalog contains four supported tools | Broader project-level navigation cases; workspace/symbol is not advertised |
| Source log locations | Real resolve/context/stats/annotate calls return complete results on an owned log/map/source fixture | Large or malformed log cases |
| Entry fields | Real explain/validate/decode calls pass the documented two-beat example: 0xab234 with opcode=4, route=0x23, payload=0xab and matching source provenance | Additional layouts, bit orders and invalid-input cases |
| Bazel RTL lint | Real soc_lint invokes VCS-only axi_narrow lint; compilation/linking completes and the check reports 21 warnings, zero errors/fatals | Clean positive fixture; existing design warning failures are not a tool PASS |
| Bazel integration | Real workspace validation, target listing, dependency/build-graph queries and vendor-entry snippet generation; corrected parser identifies 24 actual repositories | Three real missing IP paths remain; other build operations unverified |
| RTL integration | All ten tools passed the owned 15-case lifecycle/negative fixture after `db47a17` (`34803830123`); a generated parameterized wrapper also passes registered VCS compile/elaboration (`34806987896`) | Remaining generated-top variants have not been compiled or simulated; not complete SystemVerilog syntax support or project-level connectivity signoff |
| Library preparation | After adapting kit `7e3eb42`, all seven actual helper `--no-run` cases pass (ETX run `34805152537`): numeric bus whitespace preserved, unsupported types/arrays rejected, ordinary ANSI/non-ANSI generation, explicit symbolic-width warning, Tcl generation, existing-file preservation and collision rejection | This is skill-helper preparation, not MCP or compiled DB acceptance. There is no registered library MCP and no `lc_shell` on the tested PATH; compiler/license availability remains unverified. The LC backend was not changed |
| CRG, memory-map, Excel and clock diagrams | Seven real generator calls produce nonempty outputs from copied examples; generated Draw.io XML and Excalidraw JSON parse successfully | Generated HDL compilation, project semantics and diagram visual review |
| OpenROAD | Actual isolated config/SDC generation and empty-output status query pass | Local synthesis cannot start without orfs_dir/SILICON_CREW_ORFS_DIR; bounded runner discovery found no ORFS path or openroad/yosys on PATH. Container execution remains unverified |
| Memory wrappers | Actual catalog-backed MCP generation; corrected 96x24 logical interface maps to a sufficient 128x32 macro; VCS compile/simulation report passes the bounded address/mask test | Other memory/FIFO variants, physical lib/lef availability, and full signoff remain unverified |
| Exported upstream memory adapter | Pristine snapshot checks, locked export and 9 capacity tests pass; isolated ETX MCP initialization and status pass | Generation fails without a configured ORFS platforms root. This newer exported source is not the previously validated project generator; do not replace it automatically or use an empty directory to bypass the dependency check |
| Optional Make adapter | All ten actual cases pass after kit `6848cbd` adaptation: new project/chip/IP scaffolds, duplicate preservation, shallow/recursive/text filelists, invalid-backend rejection, and registered VCS compilation/elaboration of a generated parameterized wrapper (`34806987896`) | No simulation, regression, synthesis, CDC, GUI or other backend acceptance; use only for Make projects, not the consumer's Bazel flow |
| Other disabled generic generators | Initialize and tool discovery where implemented | Individual functional fixtures; not enabled in normal sessions; absent upstream implementations remain unavailable |
| Atlassian and HTTP drawing | Atlassian discovery only; drawing untested | Authorized non-mutating service checks; never create issues merely to test |

Project-only helper migration passed 13 checks, including generated-file
synchronization and existing instruction budgets. The old script paths remain
compatibility launchers. None of these results proves full-project signoff.

Native RTL/DV guidance was checked on Claude Code 2.1.267 (ETX run 34765507485):
14.93s and 10.31s respectively, no timeout, no checkout changes. The DV answer
kept simulation opt-in and did not make regression/coverage/synthesis/CDC
automatic requirements. Only three read-only tools were allowed by the test;
this is not evidence of unrestricted execution safety. Also, RTL-only VCS lint
can compile and elaborate RTL: “no DV testbench” must not be generalized into
“no elaboration.”
