---
paths:
  - "**/BUILD"
  - "**/BUILD.bazel"
  - "**/*.bzl"
  - ".claude/skills/soc-build-bazel/**"
---

# Registered tool routing (Bazel)

Use the registered `soc-build-bazel` server for this project's build flow.
Logical notation below is `server.tool`; Claude Code exposes names such as
`mcp__soc-build-bazel__soc_lint`. Read the current input schema before calling.

| Work | Registered tool | Important input / scope |
|---|---|---|
| RTL lint | `soc-build-bazel.soc_lint` | `module`: RTL block name; VCS-only `//hw/rtl/<module>:lint_test`, not DV files |
| RTL unit test | `soc-build-bazel.soc_unit_test` | `target`: concrete `//hw/rtl/...:<target>` verified as `verilog_rtl_unit_test`; `simulator`: `vcs` or `xcelium`; explicit execution only |
| DV compile only | `soc-build-bazel.soc_comp` | `module_dir`: DV bench name/path; `test`: optional concrete test; simmer `--no-run` |
| One simulation | `soc-build-bazel.soc_sim` | `test`: actual test name; `module_dir`: DV bench; compiles and runs |
| Regression | `soc-build-bazel.soc_regress` | Inspect schema and actual execution scope before selection |
| Coverage | `soc-build-bazel.soc_coverage` | Inspect schema and scope; not an automatic DV check |
| Synthesis (preferred Flowkit) | `soc-build-bazel.soc_syn_pr` | `block`: validated direct child of `hw/pd/syn_pr`; fixed `syn_pr.py --syn_only` route, explicit execution only |
| Synthesis (compatibility) | `soc-build-bazel.soc_syn` | `module_dir`: RTL module; Bazel/DC `:netlist` route, inspect supported target and returned evidence |
| CDC | `soc-build-bazel.soc_cdc` | Inspect schema and actual target before selection |
| Dependency query | `soc-build-bazel.soc_flist` | `module_dir` for RTL or concrete `target` for DV; query only, not a compile |
| Waveform viewer | `soc-build-bazel.soc_verdi` | Use current schema and approved waveform inputs |
| Module discovery | `soc-build-bazel.list_modules` | Discover available RTL modules |

## Example argument objects

Replace placeholders with facts discovered from this checkout; examples do not
authorize execution. The tool name precedes each JSON argument object.

`soc-build-bazel.soc_lint`
```json
{"module": "<rtl_module>"}
```

`soc-build-bazel.soc_unit_test`
```json
{"target": "//hw/rtl/<rtl_package>:<unit_test_target>", "simulator": "vcs"}
```

`soc-build-bazel.soc_comp`
```json
{"module_dir": "<dv_bench>", "test": "<actual_test>", "simulator": "vcs"}
```

`soc-build-bazel.soc_sim` — only after the engineer selects simulation
```json
{"module_dir": "<dv_bench>", "test": "<actual_test>", "simulator": "vcs", "seed": 1}
```

`soc-build-bazel.soc_flist`
```json
{"target": "//<actual_dv_package>:<actual_target>", "simulator": "vcs"}
```

## Execution and evidence

- Follow `.claude/CLAUDE.md` **DV check menu** for authorization and reporting.
  An available test or a merge/signoff risk label does not select execution.
  A synthesis selection must identify the backend: prefer `soc_syn_pr` for the
  project Flowkit block flow; retain `soc_syn` only for the Bazel/DC compatibility
  route. Never run or substitute both silently.
- EDA uses registered MCP tools only; never fall back to shell/Bazel/Make or
  direct simulators. Missing tools or missing subagent permissions are blockers.
- `soc_sim` compiles before running. Do not add a redundant `soc_comp` unless
  separately selected. `soc_lint` cannot validate DV syntax.
- `soc_unit_test` performs real RTL test execution after validating one concrete
  target. It does not emit `loop_evidence`, a source fingerprint, or immutable
  artifacts, so its result alone cannot close a pipeline stage.
- Integration checks use the actual `soc-integrate-bazel` tools, such as
  `validate_workspace`, `validate_ip_defs`, and `check_module_deps`; do not
  invent `.compile`, `.test`, generated-top or other aliases.
- Use other enabled servers only for their responsibilities in root `CLAUDE.md`.
  Registered-but-disabled generators remain prohibited.
- Report real return status and log evidence, plus run IDs, fingerprints and
  artifact paths when emitted. Do not fabricate missing fields. Missing or
  incompatible evidence leaves delivery state open. Structural synthesis is
  not timing closure; WNS/TNS must come from a real STA report.
