# On-demand MCP servers

Enable only servers needed for the task; enabling every server is not required.
Registration, configuration approval, connection, and callable tools are distinct.

## Task routing

| Task | Server |
| --- | --- |
| Project context and regression artifacts | `claude-kit` |
| SystemVerilog source search, structure, definitions, references and parse diagnostics | `soc-lsp` first |
| Selected Bazel checks | `soc-build-bazel` |
| Build/dependency integration checks | `soc-integrate-bazel` |
| Managed verification debug and coverage | `xverif` |
| Register table generation | `silicon-crew:excel-yml-gen` |
| SRAM wrappers | `silicon-crew:gen-memwrap` |
| Chip address map | `silicon-crew:gen-asic-memmap` |
| CRG requirements | `silicon-crew:crg-req-to-design` |
| Clock/reset tree diagrams | `silicon-crew:cr-tree-diag-gen` |
| Jira or Confluence | `atlassian-dc` |

## Before using a server

1. Resolve the server and tool from project registrations or the task profile.
2. If disabled, enable that server using the available supported session controls.
   This project authorizes task-required enablement; do not ask for approval again.
   Preserve unrelated server settings and managed restrictions.
3. Verify connection and tool availability before calling it. A settings edit alone
   is not proof that the running session loaded the server.
4. If enablement, reload, trust, or authentication requires human interaction,
   identify the exact server and required action in `/mcp`; continue independent work.
   Do not invent tools or results, or enable unrelated servers as a workaround.

For EDA use the registered MCP server; an unavailable server does not authorize
shell EDA commands. Enabling a server does not authorize new simulations or checks;
retain the engineer's existing check selections.

For SystemVerilog/Verilog source searches, prefer `soc-lsp` before reading source
text. Use scoped `rg` only for unknown file paths, literal text/macros, unsupported
queries, or unavailable/incomplete LSP results; identify the gap. Keep file ranges
and result pages bounded. Consult `.claude/references/soc-lsp-parse.md` when
configuring an index or retrieving diagnostics. Verible findings do not satisfy
compiler, simulation or DV checker gates. Consult
[Claude Code MCP documentation](https://code.claude.com/docs/en/mcp) for
client-version-specific controls; do not assume one settings key controls all scopes.
