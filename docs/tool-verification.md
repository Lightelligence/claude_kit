# Tool verification snapshot

[简体中文](tool-verification.zh-CN.md) · [Usage, differences and prompts](tool-selection.md)

This on-demand reference records bounded acceptance, not signoff for every tool
argument, design or agent workflow. Do not load this table into every Claude
session. The consumer snapshot is `2e6e585` with functional kit `164fe15`,
captured on 2026-09-14 in private ETX run `34810635715`.

The user stopped additional testing before final delivery. The final instruction
edits are delivered without a new native-Claude behavioral run. Earlier core
(39), MCP (3) and adaptation (6) checks passed on the intermediate candidate;
they are not end-to-end acceptance of the final consumer. No new simulation or
external mutation was performed for these edits.

## Actual server inventory

The current catalog has **17 servers**. Default startup enables **three servers
and 23 tools**. The historical 218-tool inventory includes optional stdio
servers; it is not the default context. Schema bytes are not model tokens.

| Registered server | Default | Purpose and tested boundary |
| --- | --- | --- |
| `claude-kit` | Yes | Project context, bounded evidence and compact catalogs; actual native Claude calls pass. Compact catalog: nine tools, 2,523 schema bytes. |
| `soc-build-bazel` | Yes | Project Bazel execution. Actual RTL-only VCS lint reaches compile/link and reports 21 design warnings; the check fails, not a clean design PASS. DV compile and selected simulation are different operations. |
| `soc-lsp` | Yes | Four supported file-navigation tools; eight real calls across two workspaces pass. Not compiler or behavior validation. |
| `soc-integrate-bazel` | No | Seven read-only build-graph/vendor operations tested; 24 vendor repositories parsed. Three missing project IP paths remain. |
| `silicon-crew:soc-build` | No | Make projects only: ten real cases, including generated-wrapper VCS compilation, pass. Not a replacement for the Bazel adapter. |
| `silicon-crew:soc-integrate` | No | All ten tools pass 15 owned lifecycle/negative cases; a parameterized wrapper compiles. Not general SystemVerilog or whole-chip signoff. |
| `silicon-crew:yml2reg` | No | All 13 entrypoints produce outputs; shipped APB/AHB/DAB RTL compiles. RAL integration is deferred below. |
| `silicon-crew:gen-asic-memmap` | No | Actual address-map generation produces outputs; applicable machine-readable formats parse. No project address-space signoff. |
| `silicon-crew:gen-memwrap` | No | Existing consumer generator passes a bounded 96x24-to-128x32 generation/HDL fixture. The newer exported adapter separately needs ORFS platforms; do not replace the working generator automatically. |
| `silicon-crew:excel-yml-gen` | No | Actual spreadsheet conversion produces outputs. Register source conversion is not bus-semantic verification. |
| `silicon-crew:crg-req-to-design` | No | Actual requirements-to-design generation produces outputs. PLL/clock architecture still needs engineering review. |
| `silicon-crew:crg-gen` | No | Shared CSR backend: 205 matching connections/ports, VCS compile/elaboration, and unsupported-AHB error propagation pass. Full CRG integration is deferred below. |
| `silicon-crew:cr-tree-diag-gen` | No | Actual diagram generation; Draw.io XML/Excalidraw JSON parsing passes. Visual layout not certified. This is local generation, not the HTTP drawing service. |
| `silicon-crew:soc-openroad` | No | Isolated config/SDC generation and status pass; synthesis blocked by absent ORFS setup. |
| `xverif` | No | Bounded bit, SVA, entry, source-location and FSDB queries pass. Native NPI coverage database opening fails; isolated parser fixes are not shared-runtime deployment. |
| `atlassian-dc` | No | Current discovery: 98 tools / 115,008 compact-JSON UTF-8 schema bytes. Actual own-user profile lookup passes (`34810934608`); other operations are not certified by that lookup. |
| `drawio` | No | Excluded from further work at the user's request. Retained evidence: HTTP 403; isolated native Claude startup timed out at 150 s (`34811483486`). No successful business call is established. |

See the [detailed capability matrix](tool-selection.md#etx-verification-scope-updated-2026-09-14)
for retained run IDs and limitations. Raw vendor logs and service responses
remain in private owned ETX fixtures, not this repository.

## Skills, agents and helpers

The same snapshot contains **30 skills and nine agents**. All literal local
Markdown link targets checked in their instructions and the engineer docs exist
in the actual checkout. File discovery and link checks do not certify behavioral
quality, automatic selection or every workflow. Project-only names, conventions
and the complete inventory remain in `.claude/docs/SKILLS.md`; do not copy them
into the reusable kit's startup rules.

- Skills guide decisions; MCP tools perform registered operations; agents divide
  responsibilities; scripts implement tools or maintenance.
- Keep `soc-build` versus `soc-build-bazel`, RTL versus build-graph integration,
  and offline waveform versus live simulator control distinct.
- `xwiki` and `lib-db-gen` are not extra MCP servers. The library helper passed
  seven real `--no-run` preparation cases; `.db` compilation still needs the
  actual compiler/license setup.
- Actual shared xwiki helpers at `cc839de` pass seven isolated cases
  (`34811483486`): missing-path rejection, non-writing dry-run, 15-file valid
  initialization, existing-file preservation, invalid object type rejection,
  broken-link rejection and restored-fixture validation. No project ingest or
  live wiki modification was performed.
- Seven project-only Claude helpers now live in `.claude/scripts/`; existing
  root entrypoints are compatibility launchers. General build tools stay put.

## Remaining boundaries

**Deferred by the user:** RAL adapter/portability work and full CRG top primitive
integration. Do not resume either as part of final documentation or other-tool
acceptance. Existing CSR-only results remain valid, but are not full CRG PASS.

**External or deliberately unexercised:** native NPI database-open crash; missing
ORFS platforms/toolchain; three missing project IP paths; library compiler/license;
live simulator control; external Jira/Confluence writes;
diagram visual review; full project semantics and unrestricted agent workflows.
No backend replacement, simulation, dummy cells, issue creation or credential
change was used to manufacture acceptance.
Draw.io, gen-memwrap, xsimdebug, lib-db-gen and rtl-design are separately
excluded by the user's request; do not retry or repair them. Their identified
instruction issues remain unresolved. The gen-memwrap skill YAML issue remains
unfixed; its previous bounded generator results do not establish skill loading.

Separate source fixes remain under review in
[xverif PR 2](https://github.com/Lightelligence/xverif/pull/2) and
[xverif PR 3](https://github.com/Lightelligence/xverif/pull/3).
They are not implicitly installed by updating the kit pin.

## Efficient daily use

Start with ordinary Claude Code and the three default servers. Select only the
profile needed for a debug, generator or documentation task; confirm `/mcp`.
Retrieve one relevant schema, use bounded/batched queries, and reuse verified
project context. Do not enable all 98 Atlassian tools for normal RTL/DV editing.

```text
Explain which currently registered tool can answer <question>.
Show its required inputs and one minimal example. Do not execute it yet.
```

```text
Use dv-engineering to implement <scenario> in <testbench>.
Do not simulate. Show applicable validation choices, accept my selected subset,
and report each selected result separately without adding unselected checks.
```

Jira screenshot upload must use an actual registered **Jira attachment** tool,
if available. A Confluence attachment operation targets a different resource;
do not upload there as a substitute. When no Jira upload capability is
registered, report that limitation and let the engineer attach the image in
Jira. Successful profile lookup is not permission to create or modify an issue.
