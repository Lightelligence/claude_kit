# Focused RTL and DV entrypoints

[中文](rtl-dv-entrypoints.zh-CN.md)

Choose the work first, not a long list of tools. These optional attachment
templates expose four native Claude skills per domain without copying the
underlying guidance or changing MCP server/tool names.

| Work | RTL template | DV template | Execution boundary |
| --- | --- | --- | --- |
| Implement | `rtl-design` | `dv-test` | Edit the requested scope; no automatic simulation |
| Review | `rtl-review` | `dv-review` | Read-only; RTL logic vs stimulus/checkers/coverage |
| Diagnose a failure | `sim-debug` | `sim-debug` | Existing compile/simulation evidence first; no automatic rerun |
| Missing project facts | `project-context` | `project-context` | Only missing facts; not a mandatory startup checklist |

`dv-test` includes environment, sequence, scoreboard and checker development,
not only new test files. Review entrypoints share `rtl-dv-review` internally;
their descriptions and task scopes differ. Source catalog IDs and old CLI/MCP
requests remain unchanged. These native names exist only after attachment;
updating a kit pin does not create them in an existing project.

## Attach without changing project permissions

Templates are under `src/claude_kit/resources/templates/`:

- `kit-attachment.rtl-focused.toml`
- `kit-attachment.dv-focused.toml`

For a fresh/selective attachment, save the chosen template as the project's
`.claude/kit-attachment.toml` and adjust `kit_path` to the pinned kit. They do not
manage MCP/profile settings or create agents. With an existing manifest, merge
reviewed selections instead of replacing it. In particular, do not discard
`framework = "soc"`, exclusions, project aliases, rules or runtime scripts.

```bash
python third_party/claude_kit/bin/claude-kit attach --project-root . \
  --manifest .claude/kit-attachment.toml --dry-run
```

Review conflicts and retired paths before applying attachment in an idle checkout.
Attachment never removes retired files: changing a manifest in a populated
project does not, by itself, reduce the existing skill list. Preserve local
modifications and ownership evidence, and keep any retirement recoverable in Git.
Do not use `sync --force` over shared links.

The expanded skill alias format is backward-compatible with string aliases:

```toml
[aliases.skills.dv-review]
resource = "rtl-dv-review"
description = "Read-only DV review of stimulus, checkers and coverage."
scope = "Review the requested DV changes; consult RTL only as context. Do not run EDA."
```

`description` changes native discovery text; `scope` narrows the requested work
before reading the shared guide. Neither field grants execution permission or
enforces a sandbox. These are guidance wrappers, not full copies of native skill
frontmatter or arbitrary execution metadata. The shipped templates use source
skills with no separate native execution metadata. Keep specialized invocation
settings on their original entrypoints instead of assuming aliases inherit them.

## Servers and skills are different selections

Keep the registered project build and navigation backend for both domains when
it serves both. `rtl` and `dv` profiles that select the same three servers do
not filter individual MCP tools. A skill template does not filter tools either.
`session --tools <profile>` selects MCP servers only; it does not select skills,
plugins or hooks, and it never grants authorization for checks.

| Need | Existing project capability to choose |
| --- | --- |
| RTL lint | RTL-only lint; no DV syntax claim |
| DV syntax/elaboration | Compile-only TB check; not RTL lint or simulation |
| One simulation | Explicit test/bench/simulator/seed; no unrequested regression |
| Multi-test regression or coverage | Explicit specialist task, not an edit default |
| Synthesis, CDC, generators, physical design | Separate explicit engineering task |

Do not register duplicate MCP servers simply to give the same tools RTL/DV names.
Do not merge Make and Bazel backends or RTL-top generation and dependency-graph
inspection because their names look similar. Review permission keys and existing
callers before any future tool-ID migration.

## Audit before and after migration

```bash
python third_party/claude_kit/bin/claude-kit tool-audit --project-root . --format markdown
python third_party/claude_kit/bin/claude-kit tool-audit --project-root . --tools dv
```

The report now distinguishes enabled/disabled declarations and their source
files; it does not infer effective client state. It flags equivalent server
profiles, selected-but-disabled declarations, unmatched names, compatibility
entrypoints and simultaneous Make/Bazel build skills. Different scoped aliases
to the same guide are review candidates, not automatic deletion candidates.
Check actual native discovery and `/mcp` in the selected Claude version before
claiming the migration works. No token or latency reduction is implied by counts.

## Claude prompts

```text
/rtl-review Review only the reset and ready/valid changes in <RTL paths>.
Use the specification and relevant test evidence. Do not modify files or run EDA.
```

```text
/dv-test Add <scenario> using the existing sequence and scoreboard APIs.
Do not simulate. Show relevant validation choices; do not add RTL lint for a DV-only edit.
```

```text
/dv-review Review <DV diff> for stimulus gaps, checker validity and coverage.
Consult RTL only where needed to establish expected behavior. Do not run EDA.
```

```text
/sim-debug Investigate this existing failure: <run and bounded log path>.
Separate observed facts from hypotheses. Do not rerun simulation without my selection.
```
