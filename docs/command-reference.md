# claude_kit Command and Tool Reference

[Back to the English README](../README.md) | [简体中文](command-reference.zh-CN.md)

This is the fast lookup guide for using `claude_kit` from a consumer RTL/DV repository. It describes the repository-local CLI, the read-only MCP tools exposed to Claude Code, the reusable roles/skills/packs, the project profile, and the normal workflow for making changes under `hw/`.

Use this document when you already know what you want to do and need the shortest path to the correct command or Claude Code prompt.

## 1. The shortest path

From the consumer project root:

```bash
CLAUDE_KIT_BIN=third_party/claude_kit/bin/claude-kit

# Confirm the pinned kit and project profile.
python3 "$CLAUDE_KIT_BIN" version
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict --json

# See the available reusable pieces.
python3 "$CLAUDE_KIT_BIN" list roles
python3 "$CLAUDE_KIT_BIN" list skills
python3 "$CLAUDE_KIT_BIN" list packs
python3 "$CLAUDE_KIT_BIN" list providers
python3 "$CLAUDE_KIT_BIN" list workflows

# Route a task before reading a large amount of context or editing files.
python3 "$CLAUDE_KIT_BIN" plan \
  --project-root . \
  --task "Review and fix the AXI4 response path in hw/" \
  --json
```

Then start Claude Code from the same project root:

```bash
claude
```

When `.mcp.json` contains the generated `claude-kit` entry, Claude Code starts the bridge automatically. The normal daily interface is Claude Code; the shell commands above are useful for bootstrap, diagnostics, scripts, and CI.

## 2. Quick lookup by intent

| Goal | CLI | Claude Code / MCP |
| --- | --- | --- |
| Check the kit version | `version` | Ask Claude to report the connected kit version or use `get_project_profile` for profile state |
| Validate profile and permissions | `doctor --strict --json` | `get_project_profile` |
| Discover roles | `list roles` | `list_roles` |
| Discover protocol/VIP packs | `list packs` | `list_packs` |
| Discover skills | `list skills` | `list_skills` |
| Discover registered external providers | `list providers` | `list_providers` |
| Discover workflows | `list workflows` | `list_workflows` |
| Decide how to approach a task | `plan --task ...` | `plan_task` |
| Load selected role/pack/skill guidance | `context ...` | `resolve_context` |
| Summarize configured RTL/DV roots | `inspect --json` | `inspect_design` |
| Read a bounded log or report | `artifact read ...` | `read_artifact` |
| Find external compile/simulation artifacts | `artifact discover ...` | `discover_regression_artifacts` |
| Read an external compile/simulation log | `artifact read-regression ...` | `read_regression_artifact` |
| Validate an evidence JSON file | `evidence check ...` | `review_evidence` |
| Show the engineer-selectable check menu | `checks` | `list_checks` |
| Run a project-owned command | `check <name>` | `run_check` only when the bridge was explicitly started with `--allow-exec` |
| Run several selected checks and collect reports | `check-batch ...` | `run_checks` only with `--allow-exec` |

The CLI and MCP bridge share the same profile, path validation, catalogs, and evidence rules. The MCP bridge is an interface for Claude Code; it is not a separate planner or build system.

## 3. Conventions and safety boundaries

### Run from the project root

All project paths are normally relative to the consumer project root. Starting Claude Code or the CLI from the root makes `.ai/project.toml`, `.mcp.json`, `hw/`, logs, and profile commands resolve consistently.

```bash
cd /path/to/consumer-project
python3 third_party/claude_kit/bin/claude-kit doctor --project-root . --strict
claude
```

The wrapper can be invoked directly after making it executable, but `python3 third_party/claude_kit/bin/claude-kit ...` works even when the checkout does not preserve the executable bit.

### The profile is the source of truth

The kit does not guess project directories, targets, test names, simulator arguments, or permissions. The profile declares them in `.ai/project.toml`.

For RTL/DV projects, the default template includes a writable hardware tree:

```toml
[roots]
hw = ["hw"]
rtl = ["rtl"]
dv = ["dv"]
testbench = ["tb"]

[permissions]
writable = ["hw/**", "rtl/**", "dv/**", "tb/**", "docs/**", ".ai/overrides/**"]
deletable = []
read_only = ["third_party_vip/**", "generated/**", "out/**"]
forbidden = [".git/**", "secrets/**", "**/*.key"]
```

`roots.hw = ["hw"]` tells `inspect_design` and context generation where the hardware tree is. `permissions.writable = ["hw/**"]` authorizes edits and evidence changes there. `permissions.deletable` is a narrower, explicit scope for audited cleanup of obsolete files; it does not authorize ordinary edits. These are independent declarations: adding one does not implicitly add the other.

The kit is allowed to read and write `hw/**` when the project profile declares it as writable. It must still respect `read_only`, `forbidden`, symlink, project-root, and evidence checks.

### Read-only first, execution second

The following are read-only or planning operations:

- `doctor`, `list`, `plan`, `checks`, `context`, `manifest`, `inspect`, and `artifact read`;
- the default MCP tools;
- profile and catalog reads from Claude Code.

Build, lint, compile, simulation, regression, and collection commands are project-owned. They must be declared under `build.commands`; commands marked `confirmation = "required"` need explicit confirmation. A command whose `kind` is `simulation` or `regression` always needs explicit confirmation, even when `confirmation` is omitted or `optional`. Licensed or remote workloads should remain behind the project wrapper and the project's approved runner flow.

For a newly created or modified DV test, the default implementation path ends
with planning, static/lint checks and evidence. It does not start simulation or
regression. Ask before running an approved focused test, or explicitly delegate
that execution to the `commander` role.

## 4. CLI reference

Set a short wrapper variable once in a shell session:

```bash
CLAUDE_KIT_BIN=third_party/claude_kit/bin/claude-kit
```

Every example below can also use an installed `claude-kit` executable instead of `python3 "$CLAUDE_KIT_BIN"`.

### Common options

Most project-aware commands accept:

| Option | Meaning |
| --- | --- |
| `--project-root PATH` | Consumer project root. Defaults to the nearest Git root when omitted. |
| `--profile PATH` | Profile path relative to the project root. Usually `.ai/project.toml`. |
| `--json` | Emit machine-readable JSON where supported. |

### `version`

Show the kit version pinned by the checkout or submodule.

```bash
python3 "$CLAUDE_KIT_BIN" version
```

Use this to distinguish a stale submodule from a current kit checkout. It does not validate the project profile.

### `init`

Create the minimal project integration files without touching RTL, DV, vendor, generated, or build files.

```bash
python3 "$CLAUDE_KIT_BIN" init \
  --project-root . \
  --kit-path third_party/claude_kit
```

Normal initialization creates or proposes:

```text
.ai/project.toml
.claude/CLAUDE.md
.claude/skills/rtl-dv-kit/SKILL.md
.claude/skills/<kit-skill>/SKILL.md
```

Useful modes:

```bash
# Only the integration skill; materialize the rest later with sync.
python3 "$CLAUDE_KIT_BIN" init --project-root . --minimal

# Keep the project-side skill tree empty.
python3 "$CLAUDE_KIT_BIN" init --project-root . --no-skills

# Generate the adapter contract template.
python3 "$CLAUDE_KIT_BIN" init --project-root . --with-adapter

# Add or refresh only the claude-kit MCP entry in .mcp.json.
python3 "$CLAUDE_KIT_BIN" init --project-root . --with-mcp

# Explicitly replace kit-generated files.
python3 "$CLAUDE_KIT_BIN" init --project-root . --force
```

`init` does not enable executable MCP tools. It preserves unrelated project MCP servers. Complete the generated profile before treating `doctor` as an acceptance check.

### `sync`

Materialize or refresh the kit-provided Claude Code skills.

```bash
python3 "$CLAUDE_KIT_BIN" sync --project-root .
python3 "$CLAUDE_KIT_BIN" sync --project-root . --force
```

Without `--force`, existing files are preserved. With `--force`, only kit-managed skill paths are replaced; the profile, project rules, source files, and MCP servers are not changed. The sync is recursive: skills such as `xverif` include their `references/`, scripts, specs, and examples, not only the top-level `SKILL.md`.

### `doctor`

Validate the profile, roots, commands, roles, packs, adapter contract, and permission boundaries.

```bash
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict --json
```

Use `--strict` before editing, after profile changes, after submodule changes, and before handoff. A strict failure is a gate, not a suggestion to bypass the profile.

Typical checks include:

- profile schema and project identity;
- missing or escaping root paths;
- writable/read-only/forbidden overlap;
- `build.commands` argv and cwd;
- referenced roles, packs, and optional adapter functions;
- command confirmation policy.

### `list`

List the reusable catalogs.

```bash
python3 "$CLAUDE_KIT_BIN" list roles
python3 "$CLAUDE_KIT_BIN" list packs
python3 "$CLAUDE_KIT_BIN" list skills
python3 "$CLAUDE_KIT_BIN" list providers
python3 "$CLAUDE_KIT_BIN" list workflows

python3 "$CLAUDE_KIT_BIN" list skills --json
python3 "$CLAUDE_KIT_BIN" list providers --json
```

Text output is convenient for a human. JSON output is useful for scripts and for asking Claude Code to choose from an exact catalog.

### `list providers`

List version-pinned external provider contracts bundled by the kit. A provider
describes the Claude-facing skills, project-owned MCP server name, expected
backend choices, and required tool contract; it does not install or vendor an
EDA runtime.

```bash
python3 "$CLAUDE_KIT_BIN" list providers
python3 "$CLAUDE_KIT_BIN" list providers --json
```

For the bundled `xverif` provider, use the JSON output to verify the upstream
repository, exact commit, skill IDs, server name, and required xdebug tools
before adapting a consumer project. The project still owns `.mcp.json`,
`XVERIF_HOME`, Python/environment selection, licenses, and direct-versus-LSF
backend configuration.

Claude Code equivalent:

```text
Call list_providers. Show the xverif upstream commit, skills, MCP server name,
required tools, and runtime prerequisites. Do not start a session or run EDA.
```

### `plan`

Route a task to the smallest reusable workflow without executing project commands or modifying files.

```bash
python3 "$CLAUDE_KIT_BIN" plan \
  --project-root . \
  --task "Add an APB wait-state negative test for the hardware under hw/" \
  --json
```

Override routing when the task category is already known:

```bash
python3 "$CLAUDE_KIT_BIN" plan \
  --project-root . \
  --workflow dv-change \
  --role dv-engineer \
  --pack protocols.apb \
  --task "Add an APB wait-state negative test"
```

The result may include:

- selected workflow, roles, skills, and packs;
- source paths and hashes for selected guidance;
- available and missing profile commands;
- missing facts such as target, test selector, simulator, or source revision;
- writable/read-only/forbidden permissions;
- artifact locations and evidence requirements;
- warnings and completion gates.

`missing_facts`, `missing_commands`, and `warnings` must be resolved or explicitly recorded as blocked/skipped before execution.

### `context`

Resolve a compact Markdown context from the profile and selected reusable guidance.

```bash
python3 "$CLAUDE_KIT_BIN" context \
  --project-root . \
  --role rtl-designer \
  --pack common \
  --pack protocols.axi4 \
  --skill rtl-design \
  --skill rtl-dv-context \
  --task "Fix AXI4 response-channel backpressure in hw/" \
  --output out/claude/context.md \
  --manifest out/claude/context-manifest.json
```

Roles and packs can be repeated. Profile defaults are used when they are not specified. Skills are intentionally explicit so a large skill library does not enter every prompt. Use the skills recommended by `plan` or select the smallest relevant set.

### `manifest`

Emit only the machine-readable source manifest for a resolved context.

```bash
python3 "$CLAUDE_KIT_BIN" manifest \
  --project-root . \
  --role reviewer \
  --pack common \
  --skill rtl-dv-review \
  --task "Review the current hardware change"
```

The manifest records the project, profile, selected roles/packs/skills, task text, source paths, and hashes. It should not contain secrets or complete project source.

### `inspect`

Produce a read-only file and extension summary under the configured project roots.

```bash
python3 "$CLAUDE_KIT_BIN" inspect --project-root . --json
```

This is useful before a change to confirm that `hw/`, `dv/`, `tb/`, logs, or other configured roots exist. It does not parse SystemVerilog, run a simulator, or inspect paths outside the project root.

If `hw/` is not listed in the profile's `[roots]` table, `inspect` cannot report it as the configured hardware group even when `permissions.writable` contains `hw/**`.

### `artifact read`

Read a bounded UTF-8 project artifact such as a log, report, or evidence file.

```bash
python3 "$CLAUDE_KIT_BIN" artifact read \
  --project-root . \
  --file out/logs/smoke.log \
  --max-bytes 100000 \
  --json
```

The default maximum is 100 KiB; the hard maximum is 1 MiB. The result reports the original byte count and whether the text was truncated. The path must remain inside the project root.

### `artifact discover`

Discover compile and simulation result directories below the configured
`[artifacts.regression]` root. This is read-only and performs only a bounded
top-level lookup for the current checkout. It never scans the user's
regression parent and never chooses a newest run.

```bash
python3 "$CLAUDE_KIT_BIN" artifact discover \
  --project-root . \
  --kind simulation \
  --test focused_test \
  --run-id 42 \
  --json
```

The result includes `regression_root`, `directory`, `primary_log`,
`candidate_logs`, `lock_file`, and `locked`. Omit `--run-id` to inspect all
matching runs; when more than one result matches, `selection_required` is
true. Compile discovery uses the configured compile directory pattern and
primary log names; simulation discovery applies the test/run filters without
requiring a fixed test alias.

`discover_regression_artifacts` is the corresponding read-only MCP tool. Use
the returned path with `read_regression_artifact` instead of constructing a
path by hand.

### `artifact read-regression`

Read a bounded UTF-8 log below the configured external regression root:

```bash
python3 "$CLAUDE_KIT_BIN" artifact read-regression \
  --project-root . \
  --file /nfs/regression/<user>/<checkout-name>/sys_tb__VCS_VCOMP/cmp.log \
  --max-bytes 100000 \
  --json
```

Absolute paths returned by discovery and paths relative to the configured
regression root are accepted. The resolved path must remain below that root,
including after symlink resolution. This command only reads an existing
artifact; it does not start or rerun compile or simulation.

`read_regression_artifact` is the corresponding MCP tool. Use it for bounded
log inspection after a project build MCP tool has returned a run report.

### `evidence template`

Create a starter evidence file.

```bash
python3 "$CLAUDE_KIT_BIN" evidence template \
  --project-root . \
  --output out/evidence.json
```

### `evidence check`

Validate evidence against the profile and permission policy.

```bash
python3 "$CLAUDE_KIT_BIN" evidence check \
  --project-root . \
  --file out/evidence.json \
  --strict \
  --json
```

Strict validation checks that passed checks have evidence, artifact paths are valid, and changed paths are allowed. A change such as `hw/rtl/foo.sv` is accepted only when the profile authorizes `hw/**` under `permissions.writable` and does not classify it as read-only or forbidden. An audited deletion must use an object with `operation = "delete"` and match `permissions.deletable` (or an existing writable pattern); read-only and forbidden patterns still override it.

### `check`

Run one command declared under `[build.commands]` in the profile.

```bash
python3 "$CLAUDE_KIT_BIN" check inspect --project-root .
python3 "$CLAUDE_KIT_BIN" check lint --project-root . --confirm
python3 "$CLAUDE_KIT_BIN" check compile --project-root . --confirm --timeout 7200
```

The kit:

- executes the declared argv without shell-string concatenation;
- keeps cwd inside the project root;
- rejects undeclared command names;
- requires `--confirm` for commands with `confirmation = "required"`;
- returns status, argv, cwd, exit code, stdout, stderr, and timeout/launch errors.

Do not invent simulator arguments at the CLI. Put project-specific behavior in a project wrapper and declare that wrapper in the profile.

### `checks` and `check-batch`

Use `checks` after an RTL/DV change to show the complete, project-defined
selection menu without executing anything:

```bash
python3 "$CLAUDE_KIT_BIN" checks --project-root .
python3 "$CLAUDE_KIT_BIN" checks --project-root . --json
```

Each entry reports a normalized `category`, its `selection` policy, whether it
is `recommended`, and whether explicit confirmation is required. `syntax`,
`lint`, `compile`, `inspect`, and `filelist` are suggested when the profile
declares them. `simulation`, `regression`, `coverage`, `synthesis`, and `cdc`
are explicit engineer choices and are never auto-selected by the kit. The
category is inferred from the profile command's optional `category`, `kind`, or
project command name; the kit does not need to know a project's wrapper names.
For an MCP-backed check, declare `mcp_server` and `mcp_tool` instead of `argv`.
The menu reports the MCP endpoint, while Claude Code calls that project server
after the engineer selects it. The kit CLI does not shell out to MCP servers.

Use `check-batch` for the engineer's multi-selection. It executes selected
commands sequentially and returns one report per item plus aggregate counts.
It continues after a failure by default; add `--stop-on-error` for fail-fast
behavior. `--report` writes the same JSON under the project root.

```bash
python3 "$CLAUDE_KIT_BIN" check-batch \
  --project-root . \
  --check lint \
  --check compile \
  --confirm \
  --report out/check-batch.json
```

Do not include simulation or regression in the selected list unless the
engineer explicitly approves the workload. The project wrapper remains
responsible for Bazel, simulator, license, remote-runner, and artifact details.

### `adapter check`

Validate the optional project adapter without invoking its project behavior.

```bash
python3 "$CLAUDE_KIT_BIN" adapter check --project-root . --json
```

It checks that the adapter imports, that required functions exist, and that known function signatures accept an argument. It does not automatically resolve targets, launch tests, connect VIP, or collect artifacts.

### `mcp serve`

Run the thin MCP bridge over stdio. Claude Code normally starts this through `.mcp.json`; use the command manually only for bridge diagnostics.

```bash
python3 "$CLAUDE_KIT_BIN" mcp serve \
  --project-root . \
  --profile .ai/project.toml
```

The default bridge is read-only. Do not add `--allow-exec` unless the project owner explicitly wants the MCP server to expose the profile command runner.

## 5. MCP tool reference

The MCP tool names below are what Claude Code should call. You normally describe the task in natural language; you do not need to construct JSON-RPC messages manually. The argument examples show the structured payload that Claude Code supplies to the tool.

### `get_project_profile`

Purpose: return the validated, redacted project profile and validation status.

Arguments:

```json
{}
```

Use it first when Claude Code needs to know the project roots, `hw/` scope, build commands, artifacts, policies, or current validation issues. It does not modify files or run commands.

Expected result areas include `profile`, `project`, and `validation`; secrets are redacted.

Claude Code example:

```text
Use get_project_profile first. Summarize the configured hw, RTL, DV and testbench roots, writable/read-only/forbidden paths, available project commands, and any validation issue. Do not modify files.
```

### `list_roles`

Purpose: list reusable engineering viewpoints such as RTL designer, DV engineer, reviewer, debugger, waveform debugger, VIP integrator, and evidence reviewer.

Arguments:

```json
{}
```

Use it when the task is unclear or when you want to choose a role explicitly before `plan_task` or `resolve_context`. The result includes role IDs, summaries, versions, and source paths.

Claude Code example:

```text
Call list_roles and recommend the smallest role set for reviewing and modifying an RTL implementation under hw/. Explain why each selected role is needed.
```

### `list_packs`

Purpose: list reusable common, protocol, and VIP guidance.

Arguments:

```json
{}
```

Use it to discover IDs such as `protocols.axi4`, `protocols.apb`, `protocols.ethernet`, or `vip.generic`. A pack provides review and verification guidance; it does not replace the project's actual interface, VIP, or simulator configuration.

Claude Code example:

```text
Call list_packs. Based on the protocols actually declared by the project profile, recommend the relevant pack for a change under hw/. Do not invent a protocol mapping.
```

### `list_skills`

Purpose: list reusable Claude Code skill instructions.

Arguments:

```json
{}
```

Use it to discover skill IDs before requesting explicit context. Skills are guidance, not executable tools. They should be selected narrowly so the prompt remains focused.

Claude Code example:

```text
Call list_skills and identify the smallest skill set for an RTL change, a DV change, and a waveform/debugging task. Do not load every skill into context.
```

### `list_providers`

Purpose: list the external provider contracts that the kit knows how to
describe to Claude Code.

Arguments:

```json
{}
```

Use it before configuring or troubleshooting an external MCP provider. It is
read-only and returns provider metadata, including the pinned upstream
provenance, skill IDs, server name, backend choices, required tools, and
runtime boundaries. It does not launch the provider, inspect a waveform, open
a debug session, or execute an EDA command.

Claude Code example:

```text
Call list_providers. For xverif, summarize the pinned source commit, skills,
server name, backend options, required tools, and what remains project-owned.
Do not guess a target, action, simulator, or XVERIF_HOME path.
```

### `list_workflows`

Purpose: list task-routing workflows and their routing hints.

Arguments:

```json
{}
```

The built-in workflow families are `rtl-change`, `dv-change`, `debug`, `protocol-vip`, `review`, and `handoff`. The result also contains default roles, skills, preferred command names, keywords, and protocol hints.

Claude Code example:

```text
Call list_workflows and explain which workflow applies to a change in hw/ and which applies to a failing DV regression. Do not execute either workflow yet.
```

### `plan_task`

Purpose: route a task to roles, skills, packs, project checks, and evidence gates without executing commands.

Arguments:

```json
{
  "task": "Fix an AXI4 response-channel backpressure timeout in hw/",
  "workflow": "auto",
  "roles": ["rtl-designer", "reviewer"],
  "packs": ["protocols.axi4"]
}
```

Only `task` is required. `workflow` defaults to `auto`; `roles` and `packs` override profile/workflow defaults when supplied. `plan_task` does not accept `skills`; use its selected skill output as input to `resolve_context`.

Important result fields:

- `workflow`: selected route and completion criteria;
- `roles`, `skills`, `packs`: selected reusable guidance;
- `check_plan`: available or missing profile command definitions;
- `check_selection`: engineer-selects mode, multi-select support, and sequential report behavior;
- `missing_facts`: target, test selector, simulator, source revision, or other facts still needed;
- `permissions`: whether `hw/**` and other paths are writable;
- `artifacts` and `evidence`: where results should be collected and how they must be recorded;
- `warnings`: gates that must be resolved or explicitly recorded.

Claude Code example:

```text
Use plan_task for this request:

"Modify the smallest necessary RTL under hw/ to fix the response-channel timeout,
then add or update the corresponding DV check."

Use workflow=auto. Select only roles and protocol packs supported by the profile.
Do not run commands or edit files. Return the plan, missing facts, permission
gates, evidence requirements, and the exact skills to load next.
```

### `resolve_context`

Purpose: assemble the task-local Markdown context and a source manifest from the project profile and explicitly selected reusable guidance.

Arguments:

```json
{
  "task": "Review the APB register interface under hw/",
  "roles": ["reviewer"],
  "packs": ["protocols.apb"],
  "skills": ["rtl-dv-context", "rtl-dv-review"]
}
```

All fields are optional. Profile defaults supply roles and packs when they are omitted. Skills are empty unless explicitly supplied. This is intentional: use only the skill content needed for the task.

The result contains `context` and `manifest`. The manifest records source paths and SHA-256 hashes for the selected role, pack, and skill files.

Claude Code example:

```text
Use resolve_context for an RTL review under hw/. Use the reviewer role, the
protocol pack selected by the profile, and only the skills recommended by the
previous plan_task result. Summarize the resolved context before inspecting
source files. Do not modify anything.
```

### `inspect_design`

Purpose: return a read-only count and extension summary for the directories declared in `[roots]`.

Arguments:

```json
{}
```

It is a bounded inventory, not an RTL parser. It reports groups such as `hw`, `rtl`, `dv`, `testbench`, `vendor`, `generated`, and `docs`, including missing roots, file counts, extensions, scan count, and truncation status.

Claude Code example:

```text
Call inspect_design and report the configured hw/ files, extensions, missing roots,
and whether the scan was truncated. Do not read or modify files outside the
configured project roots.
```

### `read_artifact`

Purpose: read a bounded, project-relative UTF-8 artifact such as a log, report, or evidence file.

Arguments:

```json
{
  "path": "out/logs/smoke.log",
  "max_bytes": 100000
}
```

`path` is required. `max_bytes` defaults to 100,000 and cannot exceed 1,000,000. The result contains the project-relative path, original byte count, truncation status, and decoded text. Paths that escape the project root or follow an unsafe symlink are rejected.

Claude Code example:

```text
Use read_artifact on out/logs/smoke.log with max_bytes=100000. Extract the first
failure, the earliest relevant warning, the likely phase, and the next evidence
to collect. Do not rerun the workload or change the artifact.
```

### `review_evidence`

Purpose: validate a project-relative evidence JSON file against the profile and permission policy.

Arguments:

```json
{
  "path": "out/evidence.json",
  "strict": true
}
```

`path` is required. `strict` turns warnings into failures. Validation checks project identity, task text, check statuses, command evidence, artifact paths, skipped items, risks, and changed paths. A changed `hw/**` path passes the permission check only when `hw/**` is declared writable and not also read-only or forbidden.

Claude Code example:

```text
Use review_evidence on out/evidence.json with strict=true. Report every issue,
including missing command evidence, invalid artifacts, and paths outside the
writable scope. Do not edit the evidence file.
```

### `run_check`

Purpose: run a project-declared command through the profile allowlist.

Availability: disabled in the default MCP bridge. It is exposed only when the server is started with `--allow-exec`.

Arguments:

```json
{
  "name": "inspect",
  "confirm": true
}
```

The command name must exist under `[build.commands]`. The tool still requires `confirm=true`; the profile command's own `confirmation` policy is also enforced. Prefer read-only `inspect` first. Keep compile, simulation, regression, and licensed workloads in the approved project wrapper/runner flow.

Claude Code approval-gated example:

```text
Do not call run_check yet. First show the profile definition for the command
named inspect, its cwd, argv, confirmation policy, expected artifacts, and the
reason it is safe to run. Wait for my explicit approval.
```

### `list_checks`

Purpose: return the same read-only, engineer-selectable check menu exposed by
the `checks` CLI command.

Arguments:

```json
{}
```

Use it after the implementation or DV environment change is complete. Show the
menu and ask the engineer which names to select. Do not treat `recommended`
entries as permission to execute them automatically, and do not add explicit
simulation, regression, coverage, synthesis, or CDC entries without selection.

### `run_checks`

Purpose: execute an engineer-selected list of profile commands sequentially and
return per-check reports and aggregate counts.

Availability: disabled in the default MCP bridge. It is exposed only when the
server is started with `--allow-exec`.

Arguments:

```json
{
  "names": ["lint", "compile"],
  "confirm": true,
  "timeout": 3600,
  "stop_on_error": false
}
```

`names` must contain unique command names declared under `[build.commands]`.
The result preserves the order of selection and includes `passed`, `failed`,
`blocked`, and `not_run` counts. `confirm=true` acknowledges this selected
batch; simulation and regression commands still have their individual
confirmation gate. Ask for explicit approval before adding an expensive
workload, or delegate it to the project-approved `commander` flow. MCP-backed
entries are reported as blocked by the CLI batch runner because their actual
tool calls belong in Claude Code; use the selected server/tool from `list_checks`.

## 6. Claude Code recipes

### Verify the connection and catalogs

Paste this into Claude Code after starting it from the consumer project root:

```text
Use the claude-kit MCP server, not shell-only inspection.

1. Call get_project_profile.
2. Call list_roles, list_packs, list_skills, and list_workflows.
3. Confirm whether hw/ is a configured root and whether hw/** is writable.
4. Recommend the smallest role, skill, and pack set for an RTL change under hw/.
5. List the actual MCP tools called and any profile issue.

This is a read-only discovery task. Do not modify files or run build, compile,
simulation, regression, or licensed commands.
```

### Plan before an RTL change under `hw/`

```text
First use get_project_profile and inspect_design.
Then use plan_task for:

"Implement the requested RTL behavior under hw/, identify the corresponding DV
coverage/check changes, and preserve the existing protocol contract."

Use only roles, skills, and packs returned by the kit. Do not edit files yet.
Report the exact files or directories that are in scope, missing facts, allowed
commands, evidence requirements, and the smallest safe next step.
```

### Resolve context for a protocol review

```text
Use list_packs to find the protocol pack actually relevant to this project.
Use resolve_context with reviewer, the selected protocol pack, and the smallest
relevant review/context skills. Then review only the files under the configured
hw/ root and report findings with paths and line numbers.

Do not modify files and do not infer a protocol that is not present in the profile
or source.
```

### Review a completed check

```text
Use read_artifact on the project log and review_evidence on the evidence JSON.
Summarize passed, failed, skipped, blocked, warnings, root cause candidates,
and unresolved risks. Tie every conclusion to an artifact or command result.
Do not rerun the workload or modify source, logs, or evidence.
```

### Move from plan to edit safely

```text
The plan is approved. Before editing:

1. Reconfirm the profile and the writable scope.
2. Keep RTL implementation changes under hw/** unless the profile explicitly
   authorizes another path.
3. Use the selected RTL/DV skills and protocol pack only.
4. Show the intended file list and patch summary before making the edit.
5. After editing, review the diff and produce evidence for every check.

Do not touch vendor, generated, build, .git, secret, or read-only paths.
```

## 7. Profile setup for `hw/`

For a project whose implementation lives under `hw/`, use at least:

```toml
[roots]
hw = ["hw"]
dv = ["dv"]
testbench = ["tb"]
docs = ["docs"]
vendor = ["third_party_vip"]
generated = ["generated", "out"]

[permissions]
writable = ["hw/**", "dv/**", "tb/**", "docs/**", ".ai/overrides/**"]
read_only = ["third_party_vip/**", "generated/**", "out/**"]
forbidden = [".git/**", "secrets/**", "**/*.key"]
```

If the project also keeps a separate `rtl/` tree, add `rtl = ["rtl"]` and `rtl/**` to the writable list. Do not broaden writable scope just because a directory exists.

Validate the change:

```bash
python3 "$CLAUDE_KIT_BIN" doctor --project-root . --strict --json
python3 "$CLAUDE_KIT_BIN" inspect --project-root . --json
```

If strict evidence later reports `hw/... is outside the writable scope`, check both declarations rather than bypassing validation:

1. Is `hw` listed under `[roots]` when it needs to be inspected?
2. Is `hw/**` listed under `permissions.writable`?
3. Is any broader or narrower pattern placing the same path in `read_only` or `forbidden`?
4. Is the path actually inside the project root and not an escaping symlink?

## 8. MCP configuration for Claude Code

The generated `.mcp.json` entry is:

```json
{
  "mcpServers": {
    "claude-kit": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "third_party/claude_kit/bin/claude-kit",
        "mcp",
        "serve",
        "--project-root",
        ".",
        "--profile",
        ".ai/project.toml"
      ]
    }
  }
}
```

This connects the bridge only. The profile, adapter, project commands, simulator setup, remote runner, and evidence locations remain project-owned.

In Claude Code, check the connection with the client's MCP status view or `/mcp` when that command is available. If the server is missing:

```bash
python3 third_party/claude_kit/bin/claude-kit doctor \
  --project-root . \
  --profile .ai/project.toml \
  --strict \
  --json
```

Then inspect `.mcp.json`, the submodule path, and the Python interpreter used by the MCP configuration. Do not install the Python MCP SDK just to run the kit; the bridge includes its stdio framing support.

## 9. Common problems

### Claude Code answers without calling a kit tool

Start Claude Code from the project root. Confirm the `claude-kit` server is connected. Ask explicitly for `get_project_profile` or `list_skills` and request that the response list the actual tool calls. A shell-only answer is not evidence that MCP was used.

### `bin/claude-kit` gives a permission error

Use:

```bash
python3 third_party/claude_kit/bin/claude-kit version
```

The wrapper has a Python shebang but a checkout may not preserve its executable bit. `python3` is the stable invocation.

### `doctor` cannot find the profile

Run from the consumer project root or specify both paths:

```bash
python3 "$CLAUDE_KIT_BIN" doctor \
  --project-root /path/to/consumer-project \
  --profile .ai/project.toml \
  --strict
```

### `inspect_design` does not show `hw`

`permissions.writable` and `[roots]` are separate. Add `hw = ["hw"]` under `[roots]`, then run `doctor` and `inspect` again.

### A change under `hw/` is rejected

Add `hw/**` to `permissions.writable`, remove any overlapping `read_only` or `forbidden` pattern, and rerun strict validation. Do not solve a profile error by weakening evidence validation.

### `plan_task` reports missing commands or facts

The planner does not invent target names, simulators, test selectors, source revisions, or project wrappers. Bind the fact in `.ai/project.toml`, implement the project-owned adapter/wrapper, or record the item as blocked/skipped with a reason.

### `resolve_context` contains no skill guidance

Skills are explicit. Pass a `skills` array to `resolve_context` or `--skill <id>` to the CLI `context` command. Start with the smallest relevant skill set.

### `read_artifact` rejects a path or truncates output

Use a project-relative path under the project root. Read large logs in bounded chunks or raise `max_bytes` up to 1,000,000. The tool intentionally refuses paths outside the root.

### `check` or `run_check` is refused

Confirm that the command exists under `[build.commands]`, that its cwd exists,
and that the confirmation policy is satisfied. Commands with
`kind = "simulation"` or `kind = "regression"` require `--confirm` (or
`confirm=true` for `run_check`) regardless of the profile's optional policy.
The default MCP bridge does not expose `run_check`; this is intentional.

### MCP startup times out

Check that the MCP command uses the pinned submodule path, `python3`, the correct project root, and `.ai/project.toml`. Run `doctor` separately for profile errors. Use a manual `mcp serve` invocation only to capture bridge diagnostics; it is not the normal daily workflow.

## 10. Source and extension reference

The most useful implementation and documentation files are:

```text
README.md
README.zh-CN.md
docs/command-reference.md
docs/command-reference.zh-CN.md
src/claude_kit/cli.py
src/claude_kit/mcp_server.py
src/claude_kit/core.py
src/claude_kit/resources/templates/project.toml
src/claude_kit/resources/templates/SKILL.md
src/claude_kit/resources/claude/CLAUDE.md
src/claude_kit/resources/roles/
src/claude_kit/resources/skills/
src/claude_kit/resources/providers/
src/claude_kit/resources/packs/
src/claude_kit/resources/workflows/catalog.json
tests/test_cli.py
tests/test_mcp.py
tests/test_core.py
```

The MCP schema is defined in `src/claude_kit/mcp_server.py`. Core path, profile, planning, artifact, command, and evidence behavior is implemented in `src/claude_kit/core.py`. Tests are executable examples and should be updated when a public command or tool contract changes.

## 11. Recommended verification loop

For a normal RTL/DV task:

```text
1. Start Claude Code at the project root.
2. Confirm claude-kit MCP connectivity.
3. get_project_profile.
4. inspect_design.
5. plan_task.
6. resolve_context with only the selected roles, packs, and skills.
7. Inspect the relevant hw/**, DV, and testbench files.
8. Obtain approval for the intended edit.
9. Modify only profile-authorized paths.
10. Review the diff.
11. Run only profile-declared checks through the approved project flow.
12. read_artifact and review_evidence.
13. Report changes, commands, results, skipped checks, and risks.
```

This sequence keeps Claude Code as the main interface, keeps `hw/**` as a first-class working scope, and preserves a reproducible boundary between reusable kit behavior and project-specific RTL/DV execution.
