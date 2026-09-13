# Choosing Claude Code tools for RTL and DV

This guide is for engineers working in a project attached to claude_kit.
The project's `.mcp.json` and Claude settings determine which servers are
available. A bundled skill or a Python source file does not enable a server.

## Start with the task, not the complete tool catalog

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
| Generate register RTL/RAL or CRG | The enabled register/CRG generator | Hand-editing generated output |
| Perform synthesis, CDC or physical design | The explicitly selected project lane | Routine work automatically required after a DV change |
| Prepare a delivery | Evidence review and the project's delivery workflow | An ordinary development iteration or automatic signoff |

In a Bazel project, prefer its registered Bazel adapter. A generic Make-based
server with a similarly named `soc_comp` is not an interchangeable backend.

## What each layer does

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

## Where scripts belong

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
