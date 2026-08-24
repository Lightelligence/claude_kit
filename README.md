# claude_kit

[English] | [简体中文](README.zh-CN.md)

A reusable Claude Code kit for RTL and DV engineering.

claude_kit keeps cross-project RTL/DV roles, protocol and VIP packs, project-profile schemas, a repository-local CLI, artifact/evidence contracts, and an optional thin MCP bridge in one versioned repository. A consumer project normally needs only a pinned submodule plus a small profile or adapter.

The kit is deliberately project-neutral. It does not contain project RTL/DV source, simulator scripts, build files, waveform databases, licensed tools, or ETX runner logic.

## Status

The repository currently provides a runnable Python MVP with:

- TOML and JSON project-profile loading and validation;
- project-root discovery and path-boundary checks;
- context resolution and auditable manifests;
- eleven reusable RTL/DV roles, including waveform debugging, regression triage and explicitly delegated execution;
- eight reusable skills that can be synchronized into a project on demand;
- six task-routing RTL/DV workflows;
- common, AXI4, AXI4-Lite, AXI4-Stream, APB, AHB, Wishbone, Ethernet, PCIe, UCIe, SPI, UART, JTAG, I2C, CHI, and generic VIP packs;
- a repository-local CLI;
- read-only project inspection;
- bounded, read-only artifact and log access;
- profile allowlisted-command execution;
- profile, manifest, artifact, and evidence schemas;
- an optional project-adapter template;
- a read-only stdio MCP bridge;
- a task planner that maps work to roles, skills, packs, project commands, and evidence gates;
- project initialization templates;
- fixtures and automated tests.

The following are intentionally future work rather than hidden project-specific behavior:

- deeper RTL AST and dependency indexing;
- dedicated waveform/FSDB parsers;
- a long-running regression state machine;
- concrete adapters for individual simulators.

Those capabilities should be added behind reusable interfaces. They should not be reimplemented separately in every consumer project.

## Architecture

The recommended layering is:

~~~text
Claude Code
    |
    +-- project CLAUDE.md and project rules
    |
    +-- claude_kit (this repository, pinned to a reviewed version)
          +-- reusable roles
          +-- protocol and VIP packs
          +-- project-profile schema
          +-- repository-local CLI
          +-- artifact and evidence contracts
          +-- optional thin MCP bridge
                    |
                    v
             consumer project profile and adapter
                    |
                    v
             project RTL, DV, VIP, and tools
~~~

The core principles are:

1. Put reusable behavior in the kit; keep project facts in the profile or adapter.
2. Give Claude Code structured context through the CLI and files rather than through guessed paths.
3. Let the planner select the smallest useful workflow and context before execution.
4. Treat MCP as an interface layer, not as the RTL/DV execution engine.
5. Keep the CLI and profile workflow fully usable when MCP is disabled.
6. Do not couple the kit to ETX, bsub, or a particular scheduler.
7. Do not put project RTL/DV, SystemVerilog, Bazel files, waveforms, databases, or generated outputs in this repository.

The MCP bridge here is the Claude Code interface. It is unrelated to any project-specific SystemVerilog, UVM, or DV file that happens to contain the word MCP.

## Contents

- [Installation and quick start](#installation-and-quick-start)
- [Use as a submodule](#use-as-a-submodule)
- [Project profile](#project-profile)
- [Project adapter](#project-adapter)
- [Roles](#roles)
- [Skills](#skills)
- [Protocol and VIP packs](#protocol-and-vip-packs)
- [CLI reference](#cli-reference)
- [Command and tool reference](docs/command-reference.md)
- [Context and manifests](#context-and-manifests)
- [Workflow planner](#workflow-planner)
- [Typical RTL/DV workflows](#typical-rtldv-workflows)
- [MCP bridge](#mcp-bridge)
- [Security boundaries](#security-boundaries)
- [Development and testing](#development-and-testing)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

## Installation and quick start

### Requirements

- Python 3.11 or newer;
- Git;
- Claude Code is optional, but is needed for Claude Code project rules or MCP use;
- no third-party Python package is required for the normal kit runtime;
- simulators, VIP libraries, Bazel, Make, and other EDA tools remain the responsibility of the consumer project.

The kit does not install or configure a simulator, a license server, a remote scheduler, or ETX.

### Run from a checkout

From the repository root:

~~~powershell
python -m claude_kit version
python bin/claude-kit list roles
python bin/claude-kit list packs
~~~

On Linux, the wrapper can be invoked directly:

~~~bash
chmod +x bin/claude-kit
./bin/claude-kit version
~~~

An editable installation is optional:

~~~bash
python -m pip install -e .
claude-kit version
~~~

For a consumer project, prefer the wrapper in the pinned submodule instead of relying on a globally installed kit.

### Initialize a consumer project

Assume the kit is checked out at third_party/claude_kit in the consumer project:

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit
~~~

This generates the normal project integration files and synchronizes the standard skills.

If the project should keep only a minimal Claude Code entry point, use minimal mode and synchronize the complete skill set later:

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --minimal

python third_party/claude_kit/bin/claude-kit sync \
  --project-root .
~~~

If the project already has its own agent or skill layer, or has a managed .claude/skills path, use no-skills mode:

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --no-skills
~~~

no-skills still creates .ai/project.toml and .claude/CLAUDE.md. Run sync later if the project decides to materialize the kit skills.

Generate a thin project adapter template when the project has target, test, or VIP mappings:

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --with-adapter
~~~

Enable the optional read-only MCP bridge:

~~~bash
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --with-mcp
~~~

The normal initialization creates:

~~~text
.ai/project.toml
.claude/CLAUDE.md
.claude/skills/rtl-dv-kit/SKILL.md
.claude/skills/rtl-dv-context/SKILL.md
.claude/skills/rtl-design/SKILL.md
.claude/skills/dv-engineering/SKILL.md
.claude/skills/protocol-vip/SKILL.md
.claude/skills/rtl-dv-debugging/SKILL.md
.claude/skills/rtl-dv-review/SKILL.md
~~~

With with-mcp, init adds or refreshes only the claude-kit entry in .mcp.json. Existing project MCP servers are preserved. A conflicting claude-kit entry fails by default; use force only when the project owner explicitly wants to replace that entry. The command does not enable run_check.

With with-adapter, init also creates .ai/adapter.py and enables the corresponding adapter section in .ai/project.toml. The generated adapter is a contract template; replace its placeholder behavior with the project's real target, test, VIP, and artifact mappings.

Initialization is intentionally conservative:

- it does not modify RTL, DV, vendor, generated, or build files;
- existing files are not overwritten by default;
- force is required before replacing kit-generated integration files;
- generated profiles are templates and must be completed by the project owner;
- generated rules do not guess project paths.

After updating the submodule, skills can be synchronized without touching the profile or project rules:

~~~bash
python third_party/claude_kit/bin/claude-kit sync \
  --project-root .
~~~

### Resource layout

Reusable resources live inside the kit:

~~~text
src/claude_kit/resources/
+-- claude/CLAUDE.md
+-- roles/
+-- skills/
+-- packs/
+-- workflows/
|   +-- catalog.json
+-- schemas/
|   +-- project.schema.json
|   +-- manifest.schema.json
|   +-- artifact-result.schema.json
|   +-- evidence.schema.json
+-- templates/
~~~

The project profile and adapter contain project facts. Schemas, generic rules, skills, packs, and evidence semantics are maintained in the kit.

Run a strict profile check after initialization:

~~~bash
python third_party/claude_kit/bin/claude-kit doctor \
  --project-root . \
  --strict
~~~

Then run a read-only context check:

~~~bash
python third_party/claude_kit/bin/claude-kit context \
  --project-root . \
  --task "Check project integration without modifying source"
~~~

## Use as a submodule

### Recommended project layout

~~~text
my_rtl_project/
+-- third_party/
|   +-- claude_kit/                 # pinned to a tag or approved commit
+-- .ai/
|   +-- project.toml                # project profile
|   +-- adapter/                    # thin project adapter
|   +-- overrides/                  # project-specific additions
+-- .claude/
|   +-- CLAUDE.md                   # generated or project-maintained entry point
|   +-- skills/
+-- CLAUDE.md                       # existing project rules, if any
+-- .mcp.json                       # optional project MCP connections
+-- hw/                             # hardware implementation (normally writable)
+-- rtl/
+-- dv/
+-- tb/
+-- third_party_vip/
+-- generated/
+-- out/
    +-- logs/
    +-- reports/
    +-- waves/
    +-- coverage/
~~~

Keep responsibilities separate:

- third_party/claude_kit: reusable roles, packs, CLI, schemas, and bridge;
- .ai/project.toml: project facts, paths, targets, tests, permissions, and artifacts;
- .ai/adapter: project-specific resolution and tool entry points;
- .claude/CLAUDE.md: Claude Code project rules;
- .mcp.json: optional MCP connection configuration;
- RTL/DV/VIP/build files: remain in the project.

### Pin a reviewed version

~~~bash
git submodule add https://github.com/Lightelligence/claude_kit.git third_party/claude_kit
git -C third_party/claude_kit checkout <approved-commit-or-tag>
git add .gitmodules third_party/claude_kit
git commit -m "Add claude kit"
~~~

The project must record the kit tag, commit, internal package version, or snapshot identifier. Before updating the submodule pointer, run doctor, context, and smoke checks in a fixture or small project.

### Minimum project configuration

A minimal integration needs:

1. the pinned submodule;
2. .ai/project.toml;
3. one project command or adapter entry point;
4. one Claude Code rule entry point.

A project does not need to copy every role, protocol pack, or MCP tool. The profile expresses differences; reusable behavior remains centralized in the kit.

## Project profile

### File location and format

The default profile lookup order is:

~~~text
.ai/project.toml
.claude-kit/project.toml
.ai/project.json
.claude-kit/project.json
project.toml
project.json
~~~

TOML and JSON are supported. TOML is recommended because it is easier for project maintainers to review.

### Complete example

~~~toml
schema_version = 1

packs = ["common", "protocols.axi4", "vip.generic"]

[project]
id = "example_ip"
display_name = "Example IP"
root = "."
language = "systemverilog"
platform = "linux"

[roots]
hw = ["hw"]
rtl = ["rtl"]
dv = ["dv"]
testbench = ["tb"]
docs = ["docs"]
vendor = ["third_party_vip"]
generated = ["generated", "out"]

[roles]
defaults = ["rtl-designer", "dv-engineer", "reviewer"]

[build]
system = "project-wrapper"
simulator = "project-configured"
target = "project-target"
test_selector = "smoke"

[build.commands.inspect]
argv = ["./tools/project-cli", "inspect"]
cwd = "."
kind = "read_only"

[build.commands.lint]
argv = ["./tools/project-cli", "lint"]
cwd = "."
kind = "verification"
confirmation = "required"

[build.commands.compile]
argv = ["./tools/project-cli", "compile"]
cwd = "."
kind = "build"
confirmation = "required"

[build.commands.simulate]
argv = ["./tools/project-cli", "simulate", "--test", "smoke"]
cwd = "."
kind = "simulation"
confirmation = "required"

[vip]
axi4_interface = "axi_if"
apb_interface = "apb_if"

[permissions]
writable = ["hw/**", "rtl/**", "dv/**", "tb/**", "docs/**", ".ai/overrides/**"]
deletable = []
read_only = ["third_party_vip/**", "generated/**", "out/**"]
forbidden = [".git/**", "secrets/**", "**/*.key"]

[artifacts]
logs = "out/logs"
reports = "out/reports"
waveforms = "out/waves"
coverage = "out/coverage"

[policies]
require_evidence = true
network = "disabled"
auto_commit = false
auto_push = false
~~~

### Field reference

| Field | Purpose |
| --- | --- |
| schema_version | Profile schema version; not the kit version |
| project | Project ID, root, language, and platform |
| roots | RTL, DV, testbench, vendor, generated, and documentation scopes |
| roles | Default role selection; project-specific rules belong in project rules or overrides |
| packs | Protocol/VIP packs actually enabled by the project |
| build | Build, lint, compile, simulation, target, and test-selector facts |
| vip | Real interface names, instance counts, and mapping facts |
| permissions | Writable, explicitly deletable, read-only, and forbidden path scopes |
| artifacts | Log, report, waveform, and coverage locations |
| policies | Network, evidence, commit, and push policy |

source_revision is an optional root-level fixed fact. When the project root is a Git worktree, plan prefers the current HEAD and reports whether the worktree is dirty. The planner reads Git state but does not fetch, commit, or push.

packs is a root-level TOML field. Put it before any TOML table such as project, roots, or roles. If it is placed below a table, TOML treats it as a field of that table and the CLI will not use it as the default pack list.

### Profile validation

doctor checks:

- schema version;
- project ID;
- root types, missing directories, and path escape;
- permission paths and overlap between writable, read-only, and forbidden;
- build command argv as a non-empty string list;
- command cwd inside the project root;
- role and pack types and built-in references;
- optional adapter path and required functions;
- command confirmation policy.

doctor warns about roots that do not exist yet but may be created by the project. doctor strict treats warnings as failures.

### Command-definition rules

Project commands must point to existing Make, Bazel, FuseSoC, Python, or other project wrappers. The kit does not reimplement a project build system and does not guess simulator arguments.

Each command should declare:

- argv;
- cwd;
- optional category (`syntax`, `lint`, `compile`, `simulation`, `regression`, `coverage`, `synthesis`, `cdc`, or a project-defined category);
- kind;
- whether it is read-only;
- confirmation requirements;
- artifact locations;
- logs to retain on failure.

The optional category makes the check menu explicit and readable. If it is
omitted, the kit infers a category from `kind` and the command name. Suggested
quick checks are shown separately from explicit expensive or specialist checks;
the kit never executes a menu entry merely because it is recommended.

For a project MCP server, use `mcp_server` and `mcp_tool` instead of `argv`:

~~~toml
[build.commands.project_lint]
mcp_server = "project-build"
mcp_tool = "project_lint"
category = "lint"
kind = "verification"
~~~

The menu exposes this as an MCP-backed check. Claude Code calls the registered
project MCP tool after the engineer selects it; `claude-kit check-batch` does
not try to shell out to an MCP server.

Commands that need a license, special environment, or remote resources should be owned by the project wrapper. The kit enforces allowlists, cwd, and evidence boundaries around that wrapper.

## Project adapter

The project adapter is the thin layer that connects the generic kit to real project facts. A typical adapter may expose:

~~~text
load_project_profile()
resolve_target(name)
resolve_test(selector)
resolve_vip(protocol)
run_project_check(name)
collect_artifacts(run_id)
review_evidence(path)
~~~

An adapter may handle:

- target and test-selector resolution;
- RTL, DV, and VIP paths;
- interface names and instance counts;
- existing Linux build and simulation wrappers;
- log, waveform, coverage, and evidence collection;
- conversion from project results into generic artifact summaries.

An adapter should not:

- copy generic roles or packs;
- package project source into the kit;
- make the kit guess project directories;
- execute destructive commands without explicit confirmation;
- make ETX, bsub, or one scheduler a kit requirement.

When an adapter behavior is shared by multiple projects, consider moving it into the kit. Names and paths that belong to one project stay in the project.

## Roles

The built-in roles are:

| Role | Purpose |
| --- | --- |
| rtl-architect | Architecture, interfaces, state machines, pipelines, and design review |
| rtl-designer | RTL addition, modification, refactoring, and focused checks |
| dv-architect | Testbench structure, verification planning, and coverage model |
| dv-engineer | Tests, sequences, drivers, monitors, scoreboards, assertions, and coverage |
| vip-integration | Protocol/VIP mapping, connectivity, configuration, and smoke checks |
| debugger | Compile, elaboration, simulation, assertion, scoreboard, and timeout diagnosis |
| waveform-debugger | Waveform, transaction, timing, and state-machine analysis |
| regression-triager | Focused-to-regression selection, classification, reproduction, and comparison |
| commander | Explicitly approved simulation/regression execution and evidence capture |
| reviewer | Read-only RTL/DV review |
| evidence-reviewer | Evidence, logs, skipped checks, and delivery review |

Role behavior is intentionally similar across projects. The profile supplies architecture, source, target, test, and VIP facts.

A role should:

1. read the profile, relevant packs, role rules, and project rules;
2. perform a read-only scan and build a file/module/interface/command map;
3. state the goal, impact scope, and acceptance conditions;
4. modify only writable paths;
5. use profile-declared commands;
6. record commands, results, skipped checks, and residual risks.

If no simulation was run, state that explicitly. Do not report a change as verified merely because the code was edited.

### DV execution gate

Creating or modifying a DV test is implementation work first. The default
completion path is planning, testbench edits, profile/read-only inspection,
static or lint checks, and evidence. It does not start simulation or
regression automatically.

Before a simulation or regression, ask for approval and show the profile
command, target, test selector, simulator, expected runtime/resource cost and
artifact location. The `commander` role is available for an explicitly
approved or explicitly delegated run; it still uses only profile-declared
wrappers. A profile command with `kind = "simulation"` or
`kind = "regression"` also requires explicit `--confirm`, even when its
`confirmation` field is omitted or optional.

## Skills

Skills are Claude Code procedures that can be synchronized into .claude/skills or selected dynamically through MCP:

| Skill | Trigger and responsibility |
| --- | --- |
| rtl-dv-context | Read the profile, inspect the project, and choose the smallest useful context |
| rtl-design | Plan and implement bounded RTL changes |
| dv-engineering | Plan tests, sequences, scoreboards, assertions, and coverage |
| protocol-vip | Apply a protocol/VIP pack and verify connectivity |
| rtl-dv-debugging | Diagnose logs, assertions, scoreboards, and timeouts |
| rtl-dv-regression | Select focused-to-regression checks and preserve reproducible evidence |
| rtl-dv-review | Perform read-only RTL/DV review and delivery checks |
| rtl-dv-evidence | Record checks, artifacts, skipped/blocked items, and risks |

Normal init synchronizes all generic skills. init minimal creates only one integration skill. init no-skills creates no project-side skill files. Both minimal modes can later be followed by sync.

## Protocol and VIP packs

The built-in packs include:

| Pack | Coverage |
| --- | --- |
| common | Generic RTL/DV, reset, handshake, boundary, and evidence rules |
| protocols.axi4 | AXI4 handshakes, ordering, IDs, bursts, backpressure, and responses |
| protocols.axi4lite | AXI4-Lite register access, side effects, strobes, and responses |
| protocols.axi_stream | AXI4-Stream packets, TLAST, TKEEP, sidebands, and backpressure |
| protocols.apb | APB setup/access phases, wait states, side effects, and errors |
| protocols.ahb | AHB phases, HREADY, HRESP, bursts, and wait states |
| protocols.wishbone | Wishbone Classic/Pipelined, ACK, STALL, ERR, and retry |
| protocols.ethernet | Ethernet framing, CRC, link state, backpressure, and recovery |
| protocols.pcie | PCIe LTSSM, TLP, completions, credits, errors, and recovery |
| protocols.ucie | UCIe training, lane/width, flits, retries, flow control, and recovery |
| protocols.spi | SPI modes, chip select, bit order, edge timing, and multiple slaves |
| protocols.uart | UART baud, framing, parity, break, and overrun |
| protocols.jtag | JTAG TAP, IR/DR, IDCODE, BYPASS, and reset |
| protocols.i2c | I2C open-drain, START/STOP, ACK, stretching, and arbitration |
| protocols.chi | CHI channels, credits, ordering, snoops, and coherency |
| vip.generic | VIP version, connections, instances, clocks, resets, and smoke checks |

A pack provides domain rules, not project paths, licenses, VIP classes, library paths, or simulator macros. The project profile and adapter provide those facts.

A protocol pack should cover at least:

- protocol version and scope;
- handshake or transaction semantics;
- reset, clock, and timing assumptions;
- error, retry, timeout, and recovery behavior;
- boundary cases and negative scenarios;
- checks and evidence expected from a smoke test.

## CLI reference

For a task-oriented command lookup with MCP arguments, Claude Code prompts, `hw/**` examples, and troubleshooting, see the [Command and Tool Reference](docs/command-reference.md).

### Command overview

~~~text
claude-kit version
claude-kit init
claude-kit sync
claude-kit doctor
claude-kit list roles
claude-kit list packs
claude-kit list skills
claude-kit list workflows
claude-kit plan
claude-kit context
claude-kit manifest
claude-kit inspect
claude-kit artifact read
claude-kit check
claude-kit adapter check
claude-kit evidence check
claude-kit evidence template
claude-kit mcp serve
~~~

All commands accept project-root-aware paths. Use the wrapper from the pinned submodule when operating on a consumer project.

### version

~~~bash
claude-kit version
~~~

Displays the package version. Use this command rather than hardcoding a version in project documentation.

### init

~~~bash
claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit
~~~

Creates the smallest project integration. Existing files are not overwritten by default.

Useful options:

- with-adapter: create .ai/adapter.py and enable the adapter profile section;
- with-mcp: add the optional read-only claude-kit server to .mcp.json;
- minimal: create only the rtl-dv-kit integration skill;
- no-skills: create no .claude/skills files;
- force: explicitly permit replacement of kit-generated integration files.

init never replaces unrelated project MCP servers and does not enable run_check.

### sync

~~~bash
claude-kit sync --project-root .
claude-kit sync --project-root . --force
~~~

Synchronizes skills provided by the kit. Without force it preserves existing project skills. With force it replaces only kit-managed skill paths; it does not touch the profile, CLAUDE.md, RTL, DV, or other project files.

### doctor

~~~bash
claude-kit doctor --project-root . --strict
claude-kit doctor --project-root . --json
~~~

Performs a read-only profile and security-boundary check. Run it after initial setup, submodule updates, and profile changes.

### list

~~~bash
claude-kit list roles
claude-kit list packs
claude-kit list skills
claude-kit list workflows
claude-kit list roles --json
claude-kit list packs --json
claude-kit list workflows --json
~~~

Lists IDs, versions, summaries, and source files. Workflow output also includes default roles, skills, preferred checks, keywords, and protocol hints.

### plan

plan is the read-only RTL/DV task entry point. It does not modify source, start a simulator, or execute a profile command. It routes a task to a reusable workflow and reports project facts and command gaps.

~~~bash
claude-kit plan \
  --project-root . \
  --task "Fix an AXI4 response-channel backpressure timeout" \
  --json
~~~

The planner:

1. selects rtl-change, dv-change, debug, protocol-vip, review, or handoff from task keywords, or accepts an explicit workflow;
2. verifies that the referenced roles, skills, and packs exist;
3. uses explicit role and pack selections as overrides, otherwise using workflow and profile defaults;
4. recommends protocol packs from terms such as AXI, APB, PCIe, or Ethernet;
5. reports every profile command in an engineer-selectable check menu, classifying wrappers such as inspect, syntax, lint, compile, simulation, regression, coverage, synthesis, CDC, filelist, and artifact collection without guessing simulator commands;
6. marks quick checks as suggested and simulation/regression/coverage/synthesis/CDC as explicit selections that are never auto-run;
7. checks target, test_selector, simulator, and source_revision facts;
8. returns skill paths and hashes, permissions, artifact locations, evidence requirements, selection rules, and warnings.

Text output is convenient for a human. json output is suitable for Claude Code, scripts, and delivery records. missing_facts, missing_commands, and warnings are not necessarily planner failures, but they must be resolved or explicitly recorded as blocked/skipped before execution.

A typical plan-context-check sequence is:

~~~bash
claude-kit plan \
  --project-root . \
  --task "Add a negative APB wait-state test" \
  --json > out/plan.json

claude-kit context \
  --project-root . \
  --role dv-engineer \
  --pack common \
  --pack protocols.apb \
  --skill dv-engineering \
  --skill rtl-dv-regression \
  --task "Add a negative APB wait-state test" \
  --output out/claude/context.md \
  --manifest out/claude/context-manifest.json

claude-kit check inspect --project-root .
claude-kit check compile --project-root . --confirm

claude-kit checks --project-root . --json
claude-kit check-batch --project-root . \
  --check lint --check compile --confirm \
  --report out/reports/dv-checks.json
~~~

plan remains useful with no MCP, no simulator license, and no ETX runner. Actual checks are still owned by profile wrappers.

### context

~~~bash
claude-kit context \
  --project-root . \
  --role rtl-designer \
  --pack protocols.axi4 \
  --skill rtl-design \
  --task "Fix response-channel backpressure" \
  --output out/claude/context.md \
  --manifest out/claude/context-manifest.json
~~~

Roles, packs, and skills can be repeated. Without explicit roles or packs, profile defaults are used. Skills are not inserted automatically, so context does not grow unnecessarily; select the skills recommended by plan.

skill adds the selected SKILL.md content and hash to the context and manifest. task-file is also supported, but it must be inside the project root.

### manifest

~~~bash
claude-kit manifest \
  --project-root . \
  --role reviewer \
  --pack common \
  --skill rtl-dv-review \
  --task "Review the current change"
~~~

Outputs only a machine-readable resolved-context manifest containing the profile, roles, packs, skills, task, and source-file hashes.

### inspect

~~~bash
claude-kit inspect --project-root . --json
~~~

Read-only summary of file counts and extensions under the profile roots. It does not parse or modify RTL and does not access paths outside the profile.

### artifact read

~~~bash
claude-kit artifact read \
  --project-root . \
  --file out/logs/smoke.log \
  --max-bytes 100000 \
  --json
~~~

Reads a text artifact under the project root. The default maximum is 100 KiB and the hard maximum is 1 MiB. The result includes original byte count and truncation status. The command is read-only and rejects paths or symlinks that escape the project root.

### evidence

Create an evidence template:

~~~bash
claude-kit evidence template \
  --project-root . \
  --output out/evidence.json
~~~

Validate evidence:

~~~bash
claude-kit evidence check \
  --project-root . \
  --file out/evidence.json \
  --strict \
  --json
~~~

Evidence should identify project, task, source revision, changes, checks, skipped items, and risks. Each check has a status; passed checks should include the actual command and artifact where possible. Strict mode treats warnings as failures and checks that changed paths are inside profile permissions. Normal changes use `permissions.writable`; an intentional cleanup deletion can use an object such as `{\"path\": \"scripts/legacy_bootstrap.py\", \"operation\": \"delete\"}` when the profile declares the exact path under `permissions.deletable`. Read-only and forbidden patterns still override both scopes.

### check

~~~bash
claude-kit check inspect --project-root .
claude-kit check lint --project-root . --confirm
~~~

Only commands registered in profile build.commands may run:

- read_only commands may run without confirmation;
- commands whose confirmation is required need --confirm;
- argv is executed without shell-string concatenation;
- cwd must stay inside the project root;
- output includes status, argv, cwd, exit code, stdout, and stderr;
- startup failures and timeouts preserve the failure reason.

### checks and check-batch

`checks` displays the project-owned selection menu. It includes every declared
wrapper, its normalized category, whether it is suggested or explicit, and
whether confirmation is required. The menu is read-only; it never starts a
command.

`check-batch` accepts multiple names through repeated `--check` options or
positional names. It runs the selected checks sequentially, continues after a
failure by default, and returns a report for every selected item plus aggregate
counts. Use `--stop-on-error` only when the engineer wants fail-fast behavior.
The optional `--report` path writes the same JSON report under the project root.
Simulation, regression, coverage, synthesis and CDC entries remain explicit
choices and require `--confirm` when executed. A typical project profile can
declare the wrapper details without putting them in the kit:

~~~toml
[build.commands.project_lint]
argv = ["./tools/project-cli", "lint"]
cwd = "."
kind = "verification"
category = "lint"
artifacts = ["out/reports/lint.json"]

[build.commands.project_simulate]
argv = ["./tools/project-cli", "simulate", "--test", "smoke"]
cwd = "."
kind = "simulation"
category = "simulation"
artifacts = ["out/reports/smoke.log"]
~~~

The first entry is suggested; the second is shown as an explicit choice and
still requires engineer approval before execution.

### adapter check

~~~bash
claude-kit adapter check \
  --project-root . \
  --json
~~~

When a profile declares an adapter, adapter check validates its path, import, required functions, and known function signatures. It does not call resolve_target, resolve_test, resolve_vip, or collect_artifacts automatically. Exercise project behavior through an allowlisted profile command and record evidence.

### mcp serve

~~~bash
claude-kit mcp serve \
  --project-root . \
  --profile .ai/project.toml
~~~

The default server exposes read-only tools. run_check is exposed only with explicit allow-exec, and a tool call still needs confirm = true.

The stdio bridge supports both newline-delimited JSON, as used by the Python MCP SDK and Claude Code, and the older Content-Length framing. It chooses the response framing from the first incoming request. The project does not need to install the Python MCP SDK just to run the kit.

After bridge changes, run:

~~~bash
python -m unittest tests.test_mcp -v
~~~

## Context and manifests

Resolved context is assembled from:

~~~text
generic role guidance
  + selected protocol/VIP pack
  + project profile facts
  + task-local instruction
  + explicit user request
~~~

The CLI resolver merges roles, packs, explicitly selected skills, the profile, and the task. Project .claude/CLAUDE.md, .ai/overrides, and the user request remain in the Claude Code rule layer; the kit does not guess or silently read unrelated files.

Context contains:

1. project facts: root, path classes, tools, and commands;
2. task instructions: goal, limits, and acceptance conditions;
3. role, pack, and skill guidance;
4. the evidence contract: commands, artifacts, skipped checks, and unresolved risks.

A manifest resembles:

~~~json
{
  "schema_version": 1,
  "project": "example_ip",
  "profile": ".ai/project.toml",
  "roles": ["rtl-designer"],
  "packs": ["protocols.axi4"],
  "skills": ["rtl-design"],
  "task": "task text",
  "sources": [
    {
      "path": "roles/rtl-designer.md",
      "sha256": "..."
    }
  ],
  "warnings": []
}
~~~

A manifest does not contain complete source code and must not contain passwords, tokens, secrets, private keys, or license material.

## Workflow planner

The workflow catalog is at src/claude_kit/resources/workflows/catalog.json. It is a generic task-routing layer, not a project build system.

A workflow defines:

- applicable scope and keywords;
- default roles, skills, and pack hints;
- preferred project command names;
- required runtime facts;
- steps, completion criteria, and protocol hints.

The current workflows are:

| Workflow | Typical scope | Default focus |
| --- | --- | --- |
| rtl-change | RTL design, refactoring, interfaces, pipelines, FIFOs, reset | rtl-architect + rtl-designer |
| dv-change | testbench, sequences, scoreboards, assertions, coverage | dv-architect + dv-engineer |
| debug | compile, elaboration, simulation, assertions, timeouts, waveforms | debugger + waveform-debugger + regression-triager |
| protocol-vip | protocol mapping, VIP connectivity, and smoke | vip-integration + protocol pack |
| review | read-only correctness, diff, and evidence review | reviewer + evidence-reviewer |
| handoff | evidence, delivery, and sign-off preparation | evidence-reviewer + reviewer |

The planner selects a route and identifies missing facts. It does not make design decisions. The profile remains the source of truth for targets, tests, simulators, commands, permissions, and artifact paths.

## Typical RTL/DV workflows

### New project integration

1. Pin the kit submodule.
2. Run init to generate a profile and Claude Code entry point.
3. Fill in RTL, DV, testbench, vendor, generated, and artifact paths.
4. Register existing inspect, lint, compile, simulation, and regression wrappers.
5. Select roles and protocol/VIP packs.
6. Configure writable, read-only, and forbidden paths.
7. Run doctor strict.
8. Run plan for the first smoke task and review missing facts or commands.
9. Run a read-only profile review.
10. Run context and inspect smoke.
11. Enable MCP only if it adds value.

### RTL change

Use rtl-architect with rtl-designer:

1. Run plan with the rtl-change workflow.
2. Read the profile, relevant modules, interfaces, tests, and project rules.
3. Establish state-machine, datapath, handshake, and reset behavior.
4. State invariants, latency, ordering, backpressure, and error semantics.
5. Modify only writable paths.
6. Run the smallest lint or compile check, then the related unit simulation.
7. Review parameters, widths, signedness, queue boundaries, and recovery.
8. Record uncovered corner cases and checks that were not run.

### DV change

Use dv-architect with dv-engineer:

1. Run plan with the dv-change workflow.
2. Read the DUT interface, transactions, registers, and existing bench.
3. Separate driver, monitor, sequencer, scoreboard, reference model, and coverage responsibilities.
4. Plan positive, boundary, negative, reset, and recovery scenarios.
5. Define comparison timing, ordering, IDs, masks, latency, and tolerance.
6. Finish static/lint checks and record the implementation evidence. Ask before
   running simulation; if the user approves or delegates to `commander`, run
   one focused test before expanding to regression.
7. Review assertions, functional coverage, scoreboard evidence, simulation
   status and gaps.

A passing test is not the same as complete verification. Report important corner cases and coverage gaps.

### Protocol/VIP integration

Use vip-integration with the relevant protocol pack:

1. Run plan with protocol-vip and confirm the protocol hint.
2. Select the protocol version and pack.
3. Record real VIP version, interface, instance count, and simulator entry in the profile or adapter.
4. Check clock, reset, direction, and mapping for every instance.
5. Run reset, one-transfer, backpressure, error, and recovery smoke tests.
6. Expand to concurrency, random delay, outstanding transactions, retry, and lane/width scenarios.
7. Separate VIP warnings, protocol violations, scoreboard mismatches, and environment failures.

### Compile or simulation failure

Use debugger:

1. Run plan with debug.
2. Save the exact command, cwd, exit code, and first meaningful error.
3. Classify the failure as environment, compile, elaboration/link, runtime, protocol, assertion, scoreboard, or timeout.
4. Confirm that the log belongs to the current source, test, and seed.
5. Reduce to one test, seed, transaction, or minimal reproduction.
6. State falsifiable root-cause hypotheses.
7. Re-run the minimal reproduction after the fix, then widen the checks.
8. Preserve before/after results and artifact paths.

The kit can call a project wrapper but does not allocate licenses, submit remote jobs, or manage schedulers.

### Review and delivery

The reviewer is read-only. Use a concrete finding format:

~~~text
[P1] path:line
Problem: concrete behavior or risk
Evidence: code, log, waveform, or test
Impact: functional, protocol, timing, verification, or maintenance
Suggestion: smallest useful correction
~~~

Before delivery, confirm:

- the change matches the task scope;
- vendor, generated, build, and secret paths were not accidentally modified;
- important checks were run or explicitly waived;
- logs and reports identify the current source and test;
- failures, skips, and unresolved risks are recorded;
- no unauthorized commit, push, network access, or destructive operation occurred.

## MCP bridge

### Positioning

The MCP bridge adapts the CLI and context resolver to structured tool calls. It is not a second workflow engine.

It should:

- be disabled by default;
- reuse profile, schema, and permission logic;
- expose a small set of stable interfaces;
- keep no conversation or secret state;
- leave CLI workflows unaffected when MCP is unavailable.

### Read-only tools

The default bridge provides:

- get_project_profile;
- list_roles;
- list_packs;
- list_skills;
- list_workflows;
- plan_task;
- resolve_context;
- inspect_design;
- read_artifact;
- review_evidence.

`list_checks` is also read-only. It returns the same engineer-selectable,
multi-select check menu used by the CLI.

With allow-exec, it additionally exposes `run_check` and `run_checks`.
`run_checks` accepts a list of selected names, executes them sequentially, and
returns per-check reports and aggregate counts. Both tools require
`confirm = true` and can execute only allowlisted profile commands.

plan_task requires task. workflow defaults to auto. roles and packs can override profile defaults. The result includes workflow, roles, skills, skill_sources, recommended_packs, check_plan, check_selection, missing_facts, missing_commands, permissions, artifacts, evidence, and warnings.

resolve_context is an explicit context-reading endpoint. Besides roles and packs, it accepts a skills array. Selected SKILL.md content and hashes are returned in the context and manifest. This lets a project use init no-skills while still requesting a minimal skill dynamically through MCP.

### Connect Claude Code

A consumer project may add this to its own MCP configuration:

~~~json
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
~~~

MCP configuration is optional. The project .mcp.json only connects the bridge; the profile, adapter, and real project commands remain project-owned.

### Boundary with project DV MCP

The bridge does not read or rewrite project SystemVerilog, Bazel, UVM, or DV MCP implementations. It sees only the roots, commands, artifacts, and permissions declared by the profile.

## Security boundaries

### Paths

- paths are relative to the project root by default;
- doctor fails on overlap between writable, read-only, and forbidden scopes;
- vendor, generated, build, out, and .git are normally read-only or forbidden;
- the kit does not create source directories merely because a path is missing;
- artifact reads reject paths that escape the project root;
- artifact reads default to 100 KiB and have a 1 MiB hard limit;
- generated files do not write through symlinks during explicit overwrite;
- a project may preserve its own agent/skill mappings without the kit crossing project boundaries.

### Commands

- only profile-registered argv may run;
- commands are not assembled from untrusted shell strings;
- argv, cwd, exit code, and artifacts are recorded;
- cleaning, deletion, overwrite, commit, push, and expensive regression need explicit confirmation;
- unknown scripts are not auto-discovered and executed.

### Secrets and network

- context, manifests, and log summaries must not expose passwords, tokens, private keys, or license content;
- network is disabled by default in the profile policy;
- the bridge does not upload source, waveforms, or logs by default;
- external services must be controlled explicitly by the user and project wrapper.

### ETX

This repository does not contain ETX runner logic and does not require ETX. It does not implement:

- bsub or ETX job submission;
- runner selection or resource scheduling;
- license-server management;
- simulator installation or version switching;
- large-regression retry policy;
- a centralized result database.

A project may use any local or remote infrastructure inside its own wrapper. The kit only invokes profile-declared entry points.

## Development and testing

### Local checks

~~~powershell
python -m compileall -q src bin
python -m unittest discover -s tests -v
~~~

The repository CI workflow runs the same compile, installation, CLI, and unittest checks across supported Python versions. It does not start a simulator, submit ETX/bsub work, or require a project license.

The fixtures cover:

- role and pack catalogs;
- TOML profile loading;
- strict doctor checks;
- permission overlap;
- context and manifest source hashes;
- workflow catalog and task routing;
- skill catalog and synchronization;
- inspect roots;
- artifact path protection;
- command confirmation;
- non-destructive init behavior;
- evidence schema and artifact references;
- CLI doctor, context, check, and evidence;
- CLI artifact read;
- MCP tools/list, profile redaction, artifact read, workflow/skill listing, planning, and read-only tools.

### Add a role

1. Add it under src/claude_kit/resources/roles/.
2. Declare id, version, and scope in front matter.
3. Document goals, required reading, workflow, checks, evidence, and prohibitions.
4. Keep it project-neutral; do not hardcode project paths.
5. Update the catalog, tests, and README.

### Add a pack

1. Create src/claude_kit/resources/packs/family/name/ and its pack.json.
2. Provide id, version, kind, summary, and entry points.
3. Document protocol version, scope, reset, handshake, errors, boundaries, and validation advice.
4. Do not include project paths, VIP licenses, tokens, or simulator macros.
5. Update the pack catalog, fixtures, tests, and README.

### Add a skill

1. Add src/claude_kit/resources/skills/skill-id/SKILL.md.
2. Declare name, version, and description in front matter.
3. Write cross-project Claude Code rules only.
4. Do not hardcode project paths, targets, licenses, or schedulers.
5. Update the skill catalog, synchronization tests, and README.

### Add a workflow

1. Add a unique workflow ID to src/claude_kit/resources/workflows/catalog.json.
2. Reference only existing generic roles, skills, and packs.
3. Use profile-level logical command names instead of simulator argv, project paths, or scheduler parameters.
4. Define conservative keywords, required facts, pack hints, steps, and completion criteria.
5. Add automatic-routing, explicit-selection, missing-fact, missing-command, and protocol-hint tests.
6. Update README and CLI/MCP behavior documentation.

### Add a CLI command

Document:

- the user problem it solves;
- input, output, and exit codes;
- read/write/execute behavior;
- profile policy and confirmation rules;
- path validation;
- behavior without MCP;
- unit tests and documentation.

### Pull request checklist

- [ ] The change belongs in the generic kit rather than being an unabstracted project workaround.
- [ ] No local path, username, secret, license, or ETX hardcoding.
- [ ] Every role/pack has a unique ID, version, and scope.
- [ ] Schema, context, CLI, and fixture tests are updated.
- [ ] Command permissions and confirmation policy are documented.
- [ ] README, CLI help, and behavior agree.
- [ ] Fixtures reproduce the important behavior.
- [ ] Validation commands, results, and skipped checks are recorded.

## Troubleshooting

### Profile not found

Run from the consumer project root or pass project-root and profile explicitly. Confirm that the profile is in the default lookup path.

### doctor reports missing roots

The profile is probably still a template. Normal doctor warns; doctor strict fails. Fill in real project paths rather than hardcoding them in the kit.

### Permission overlap

A path cannot be writable, read-only, and forbidden at the same time. Narrow the globs and run doctor again.

### Role, pack, skill, or workflow not found

Check the submodule commit, ID spelling, and profile/workflow references:

~~~bash
claude-kit list roles
claude-kit list packs
claude-kit list skills
claude-kit list workflows
~~~

plan reports missing role, skill, or pack references instead of returning an incomplete plan that only looks executable.

### check is rejected

Confirm that the command is registered in build.commands, cwd is inside the project root, and add confirm when the command policy requires it.

### Context is too large

Reduce default packs and select only the role, pack, and skill needed for the current task. Keep project facts in the profile and long protocol guidance in packs. Skills enter context only when selected explicitly or requested through MCP resolve_context.skills.

### plan reports missing facts or commands

The planner is refusing to guess the project runtime. Fill target, test_selector, and simulator in build. Map inspect, lint, compile, simulate, regression, or collect_artifacts to existing project wrappers. If a command is temporarily unavailable, record blocked or skipped in evidence instead of deleting the warning.

### MCP is unavailable

Validate the CLI first:

~~~bash
claude-kit doctor --strict
claude-kit context --task "read-only smoke"
~~~

Once the CLI works, check the MCP command, args, project root, profile, and stdio framing. An MCP failure should not block the CLI workflow.

## Roadmap

Planned directions include:

1. profile migration and finer-grained path capabilities;
2. RTL module, instance, and dependency indexing;
3. richer log, coverage, waveform, and evidence parsers;
4. a formal project-adapter interface and contract tests;
5. additional protocol/VIP packs with version and hierarchy hints;
6. optional artifact-backed long-task state and regression comparison;
7. more real RTL/DV project trials with less project-side configuration;
8. keeping MCP thin rather than moving large execution logic into MCP.

Every iteration must preserve:

- no ETX coupling in the kit;
- project differences in profiles and adapters;
- usable CLI behavior without MCP;
- no consumer-project RTL/DV source in this repository.

## License

This project is licensed under the [MIT License](LICENSE).
