# Claude Code entry point

## Context and scope

Use `.claude/CLAUDE.md` and `.claude/project.toml` for project facts; reuse them
until changed. `hw/**` contains design work. Read only task-relevant rules.
Detailed rules have path scopes; explicitly read the selected role/router's
rules before work even if no matching source has been opened yet.

Establish the checkout with `git rev-parse --show-toplevel` and resolve its real
path. Keep searches and delegated work inside it, including symlink targets.
No parent, sibling or home-directory scans. External locations require explicit
user scope; the explicitly selected Bazel-generated testbench inventory authorizes only its
listed LSP sources, not searches of surrounding external directories.
Preserve user edits. Treat vendor IP/VIP as read-only unless authorized.

## Navigation and context

- SV/Verilog (`.sv`, `.svh`, `.svp`, `.v`, `.vh`, `.vp`): enable `soc-lsp` first;
  use symbols, definitions and references, then read bounded source ranges.
  Use diagnostics after edits. Scoped `rg` handles unknown paths, literal text,
  macros or unsupported/unavailable/incomplete LSP queries; identify the gap.
- SoC index: `configure_sys_tb_index` consumes the generated outputs of the
  project target in `.claude/soc-lsp.json`. Neither `verible.filelist`
  nor `soc_flist` proves full/current coverage. Read
  `.claude/references/soc-lsp-parse.md` for setup and limitations.
- Layout/spec links: `.claude/references/repository-layout.md`. Report missing or
  conflicting specs; edit generator inputs, preserving custom regions.
- Keep full logs on disk; use summaries and selected ranges. Never dump large
  files or tool results. Bound matches, bytes and delegated responses; truncated
  results are incomplete. Skip unrelated outputs/caches/vendor trees.
- Reuse unchanged evidence; refresh after source, branch or configuration changes.
  Before compact, save decisions, changed paths, evidence and next action.

## Execution and delivery

Use registered MCP servers for EDA and only engineer-selected checks. Enable
needed servers on demand and verify connection. Follow `.claude/CLAUDE.md` gates;
report results and unverified work accurately. RTK is optional; retain raw evidence.

Reuse the task's designated branch/MR; otherwise create a feature branch.
Verify, commit task changes, push and create/update the MR without repeated
approval. Explicit local-only instructions override publication. Never merge.

Shared resources linked from `.claude` are maintained in the pinned kit. Treat them as read-only in consumer work; implement reusable changes in the kit and update its pin through a reviewed dependency change. Keep project overrides as local files selected by the attachment manifest.
