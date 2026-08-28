# xverif integration

`xverif` is an optional external provider for deterministic RTL/DV evidence.
The kit carries the Claude-facing skills and a pinned integration contract; it
does not carry the xverif runtime, EDA databases, Verdi/NPI libraries or
license configuration.

## What is synchronized

The provider is recorded by
`src/claude_kit/resources/providers/xverif/provider.json` and currently points
to upstream commit `214e9cc81ba5ffe0010f5f4f2e0d6e4cfae40de6` from
[BLANK2077/xverif](https://github.com/BLANK2077/xverif).

The five synchronized Claude skills are:

| Skill | Use it for |
| --- | --- |
| `xverif` | Routing deterministic design, waveform, protocol, coverage, bit, entry, location and SVA questions. |
| `xverif-admin` | MCP session lifecycle, direct/LSF backend, transport, timeout, license and startup diagnosis. |
| `x-npi` | Authorized Python NPI analysis and bounded URG/coverage helper workflows. |
| `xsimdebug` | Explicit live VCS UCLI or Xcelium/Xrun Tcl PTY debugging when logs or xdebug evidence are insufficient. |
| `xwiki` | Authorized persistent verification-project knowledge maintenance. |

The complete skill directories are synchronized, including their `references/`
and support files. This is important: copying only `SKILL.md` would leave the
relative reference links unusable.

List the provider and skills from the kit checkout:

```bash
python third_party/claude_kit/bin/claude-kit list providers
python third_party/claude_kit/bin/claude-kit list providers --json
python third_party/claude_kit/bin/claude-kit list skills
```

## Consumer project setup

Pin the kit as a submodule, then materialize the skills in the consumer
project. The `sync` command is safe to run repeatedly; without `--force` it
preserves existing files.

```bash
git submodule add https://github.com/Lightelligence/claude_kit.git third_party/claude_kit
git -C third_party/claude_kit checkout <reviewed-claude-kit-commit>
python third_party/claude_kit/bin/claude-kit init \
  --project-root . \
  --kit-path third_party/claude_kit \
  --with-adapter \
  --with-mcp \
  --no-skills
python third_party/claude_kit/bin/claude-kit sync --project-root .
```

`init --with-mcp` adds only the `claude-kit` server. It does not add or
replace the external `xverif` server. That server belongs in the consumer
project's `.mcp.json`, where the project can supply its own licensed checkout,
Python environment, Verdi installation and scheduler settings.

## MCP configuration contract

The upstream server is started as `python -m xverif_mcp.server`. A project may
use its own wrapper, but the wrapper must preserve the same environment and
MCP contract. A direct-mode example is:

```json
{
  "mcpServers": {
    "xverif": {
      "type": "stdio",
      "command": "<python-3.11>",
      "args": ["-m", "xverif_mcp.server"],
      "env": {
        "PYTHONPATH": "<xverif-root>/xverif_mcp/src:<xverif-root>",
        "XVERIF_HOME": "<xverif-root>",
        "XVERIF_MCP_BACKEND": "direct",
        "VERDI_HOME": "<licensed-verdi-root>"
      }
    }
  }
}
```

For an LSF-backed project, set `XVERIF_MCP_BACKEND` to `lsf` and make the
project's approved LSF/simulation launcher pass the complete LSF, Verdi and
license environment to the xverif process. Do not assume that a separately
started MCP process will acquire variables that are loaded later by a
simulation job. Do not put real credentials or site-specific absolute paths
in `claude_kit`; keep them in the consumer's untracked/local configuration or
approved secret mechanism.

### Vendor environment timing and process boundaries

The ordinary Claude Code shell does not need to export `VERDI_HOME` or
`VCS_HOME` by hand. Some projects load those vendor variables only when an
explicit simulation is selected and the project's registered `simmer` or
simulation launcher starts. The kit does not auto-run a simulation just to
prepare an environment.

An xdebug action that needs Verdi/VCS must run in an xverif MCP process started
from that same approved simulation environment, or from a project-approved
wrapper/LSF launcher that inherits it. A separate `simmer` process cannot
retroactively update the environment of an already-running MCP child. If the
MCP server was started before the vendor environment became available, use the
project's supported MCP reload/restart path after selecting the simulation;
do not work around the boundary by adding site paths or credentials to the
kit. The `VERDI_HOME`/`VCS_HOME` entries in the direct-mode example are
therefore placeholders for a deliberately environment-aware launcher, not a
requirement for every ordinary Claude Code session.

### Native/runtime compatibility preflight

The Python `xverif_mcp` adapter and the native `xdebug` executable under
`XVERIF_HOME` are a versioned pair. Updating the copied skills or the Python
adapter does not rebuild an existing native executable. The adapter therefore
fails closed if the native executable cannot produce the canonical action guide;
this prevents Claude Code from selecting actions from an incomplete or stale
catalog.

In an approved, vendor-enabled environment, an administrator can perform this
read-only preflight before registering the MCP server:

```bash
printf '%s\n' \
  '{"api_version":"xdebug.v1","action":"actions","args":{"output":{"view":"guide"}}}' \
  | "$XVERIF_HOME/tools/xdebug" --json -
```

A compatible runtime returns `summary.view` equal to `guide`, together with a
non-empty `data.guide` string and the corresponding guide byte/count fields. If
the command exits successfully but returns compact `data.actions` while
ignoring `output.view=guide`, the native binary predates the action-guide
contract. Rebuild the native `xdebug` target from the exact upstream source
revision used by the Python MCP checkout, or point `XVERIF_HOME` at a matching
installed build. Do not loosen the MCP validation, copy vendor binaries into
this repository, or treat a compact action list as equivalent evidence.

The upstream xdebug documentation currently identifies Verdi `V-2023.12-SP2`
as its tested baseline and warns that NPI signatures can differ by release.
Build from the exact source revision with the same licensed environment used by
the MCP process:

```bash
cd <xverif-root>
make -C xdebug
```

If the build compiles but fails at link time with missing `npi_fsdb_*` or
`npi_util_*` symbols, the installed Verdi/NPI release is not source-compatible
with that xdebug revision. Select an installation that exports the required
NPI API, or ask the xverif owner for a reviewed compatibility change. Do not
copy proprietary libraries into `claude_kit` and do not claim the provider is
fully usable based only on MCP registration or the compact action-list probe.
The ETX runner's optional `isolated-source-build` mode performs this NPI export
preflight and fails fast with the diagnostic artifact when no compatible local
Verdi installation is available.

An optional profile declaration makes the relationship visible to the kit
without duplicating the launcher:

```toml
[providers.xverif]
enabled = true
server = "xverif"
backend = "direct"
skills = ["xverif", "xverif-admin"]
required_tools = [
  "xverif_tools",
  "xverif_debug_get_schema",
  "xverif_debug_query"
]
```

The profile declaration is metadata and validation only. It does not start an
MCP server and does not imply that a license or xverif checkout is available.

## Claude Code usage

Use the provider through Claude Code after the `xverif` MCP server is
registered:

1. For an xdebug task, call `xverif_tools` once and read the complete action
   guide.
2. Call `xverif_debug_get_schema` for the selected action; do not guess field
   names or copy the native JSON envelope into MCP arguments.
3. Open a managed session for resource-backed daidir/FSDB queries.
4. Run the smallest `xverif_debug_query` that can distinguish the current
   hypothesis, then expand only when the evidence requires it.
5. Close the session after preserving any required export or evidence.
6. Report action/tool, signal or interface, time/range, source evidence,
   completeness flags, unknowns and artifact paths.

Use `xverif-admin` for startup, transport, timeout, session or LSF problems.
Do not silently retry, reopen, change backend, or fall back to another data
source. Use `xsimdebug` only when a live simulator session is specifically
needed and existing logs or xdebug facts cannot answer the question.

## Relationship to project checks

xverif is a diagnostic/evidence provider, not a replacement for the project's
registered build and DV MCP tools. A project profile can map a logical check to
an existing project MCP tool:

```toml
[build.commands.waveform_debug]
category = "inspect"
mcp_server = "xverif"
mcp_tool = "xverif_debug_query"
```

The mapping must match the real project contract. Do not use a generic
`waveform_debug` entry to invent an action, session or signal, and do not
replace project build/compile/simulation tools with xverif. The ordinary
`claude-kit checks` menu still controls project check selection; expensive
simulation, regression, coverage, synthesis and CDC remain explicit choices.

## Updates and provenance

When upstream changes, update the copied skill directories and the provider
manifest together. Record the exact upstream commit, synchronized paths and
local validation result in the change description. Do not update the manifest
to `master` without a commit pin.

Before updating a consumer submodule, run:

```bash
python third_party/claude_kit/bin/claude-kit list providers --json
python third_party/claude_kit/bin/claude-kit doctor --project-root . --strict
python third_party/claude_kit/bin/claude-kit sync --project-root . --force
python third_party/claude_kit/bin/claude-kit context \
  --project-root . \
  --skill xverif \
  --task "Plan deterministic waveform evidence without running simulation"
```

Then use the project's registered MCP smoke/validation path to test the real
xverif server. If the validation includes a vendor-backed xdebug action, run
that probe from the same approved simulation/simmer environment that starts
the MCP process. A kit-only pass proves metadata, skill materialization and
profile contracts; it does not prove Verdi/NPI or licensed waveform access.
