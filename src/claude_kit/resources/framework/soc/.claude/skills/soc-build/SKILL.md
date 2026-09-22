---
name: soc-build
description: Scaffold and operate Make-based SoC projects through registered MCP tools. Not for Bazel projects or automatic simulation after DV edits.
---

# SoC Build

Use the registered `soc-build` MCP server. Do not import its FastMCP object directly and do not replace EDA tool calls with shell commands.

Use this skill only for a project using this Make backend. Existing Bazel projects
use their project adapter; similarly named tools are not interchangeable.

## Runtime setup

Claude Code uses the repository `.mcp.json` to register the MCP servers for this project. If the launcher reports missing Python modules, run:

```bash
.claude/scripts/setup_mcp_env.sh
```

This installs the shared runtime under `${XDG_CACHE_HOME:-$HOME/.cache}/silicon-crew/venv`, outside the repository package. Do not package `.venv`.

## Canonical project layout

New modules scaffolded by this Make backend use the following structure;
do not reorganize an existing project's layout to match it:

```text
<module>/
├── docs/
├── de/rtl/          # RTL + filelist.f/filelist.mk
├── de/lint/         # lint configuration or reviewed collateral
├── de/cdc/          # CDC configuration or reviewed collateral
├── de/formal/       # formal configuration or reviewed collateral
├── de/run/          # transient lint/build output
├── de/syn/          # SDC, synthesis and STA output
├── dv/tb/           # testbench source
├── dv/verif/        # reusable verification source
├── dv/tests/        # regression test lists
├── dv/sim/          # simulation logs/images/waves
├── dv/cov/          # coverage databases/reports
└── Makefile
```

Pipeline artifacts remain restricted to `docs/`, `de/rtl/`, `de/run/`, `de/syn/`,
`dv/tb/`, and `dv/sim/`; the additional directories are reserved for their
specialized flow configuration and collateral.

Create structure with `soc_init`, `soc_add_chip`, or `soc_add_ip`. Do not create legacy root `rtl/`, `sim/`, `syn/`, or `constraints/` directories.

## Tools

| Tool | Purpose |
|---|---|
| `soc_init` | initialize a SoC project |
| `soc_add_chip` | add a chip module |
| `soc_add_ip` | add a digital/third-party IP |
| `soc_flist` | generate a Verilog/SystemVerilog filelist |
| `soc_lint` | project-filelist lint with Verilator or SpyGlass; accepts `rtl_top` |
| `soc_cdc` | SpyGlass CDC check; accepts `rtl_top` |
| `soc_comp` | compile; accepts `top_module` |
| `soc_sim` | compile then simulate; accepts simulator/test/seed/top |
| `soc_regress` | test/seed matrix regression |
| `soc_coverage` | single or regression coverage |
| `soc_syn` | project-filelist synthesis; accepts `rtl_top` and `syn_tool` (`yosys` or `dc`) |
| `soc_formal` | Formality equivalence from an immutable registered DC snapshot; UPF is optional |
| `soc_verdi` | open Verdi; `scope=de` loads RTL/source, `scope=dv` loads sim DB/waves |

All names, simulators, tests, seeds, and job counts are validated. A nonzero process exit or timeout is an MCP tool error.

Successful `soc_sim` and `soc_syn` responses end with a machine-readable
`LOOP_EVIDENCE=<json>` line containing `run_id`, `source_fingerprint`, and
`tool_family`. The server hashes the resolved source manifest before and after
the Make target and rejects the run if RTL/filelist material changed. Pass the
emitted run ID and fingerprint to `update_state.py` when closing `verif` or
`syn`; never synthesize these values from the current checkout after the run.

## Stage use

- RTL agents call `soc_lint`; MCP allows Verilator or SpyGlass lint only; no direct EDA fallback.
- After DV edits, propose applicable inspection and compile-only checks. Run simulation, regression, coverage, synthesis, or CDC only when selected by the engineer; reuse selections already made for this task. Report each selected check's result. An approved `soc_sim` includes compilation, so do not repeat it unnecessarily. No direct Make/simulator fallback.
- Synthesis agents call `soc_syn`; use `syn_tool=dc` for Design Compiler or `syn_tool=yosys` for structural checks. Yosys output is not STA evidence.
- Formal agents call `soc_formal` with the exact `run_id` and `source_fingerprint` emitted by `soc_syn`. Plain DC snapshots run ordinary RTL-to-netlist equivalence; snapshots containing both canonical and saved UPF run the UPF-aware mode.
- Commercial simulator/license work must remain in the registered MCP process.
- SpyGlass lint is run in no-GUI mode by default because local GUI/plugin availability may vary. If GUI is explicitly requested and plugin checkout fails, do not block lint triage on the GUI; use the generated text reports under `de/run/`.
- If the project provides a registered or documented `soc-ai-kb` lookup, use it when relevant to a lint diagnostic. Otherwise reason from the tool report, RTL and local coding rules; do not invent a missing knowledge-base tool or block triage on it.
- Lint fixes are review-gated: propose the root cause, supporting report lines, and a concrete patch plan to the user. Do not apply a final RTL fix, waiver, or severity downgrade until the user confirms. Temporary repro edits must be clearly marked and restored before any commit.

For Verilog code review, read `.claude/rules/04_verilog_coding_style.md` (project coding rule; companion short contract is `.claude/rules/04_coding_style.md`) and report mandatory (M), should (S), and recommend (R) findings with file/line evidence.
