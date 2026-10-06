# Shared SoC framework

The SoC framework owns common native agents, scoped rules, generator skills,
state/evidence scripts, bounded kit MCP adapter and Verible navigation. Consumer
projects own their profiles, target mappings, runtime/site configuration, source
hierarchy, service selection and evidence. The retained upstream snapshot remains
pristine provenance; active framework resources have their own reviewed changes.

Select it through the existing transactional attachment mechanism:

```toml
schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = []
skills = []
framework = "soc"
# Optional project overrides; each exact path must exist in the framework manifest.
framework_exclude = []
```

Run `claude-kit attach --manifest .claude/kit-attachment.toml --dry-run`, review
conflicts, then attach. Existing project files are never silently replaced. For an
initial migration, compare and explicitly remove only reviewed identical or
superseded copies before attaching. Link targets are relative to the pinned kit;
keep these portable discovery links in Git when using the submodule deployment.
The local `kit-state.json` is attachment bookkeeping and can remain ignored.
Do not edit through a shared link: exclude its exact path for a project override,
or change the kit and review a pin update. Retired resources require explicit review.

Do not also select a catalog skill that owns the same framework destination
(for example `xwiki` or `rtl-dv-kit`). Keep `skills = []` for framework-owned
skills, or explicitly exclude all overlapping framework files before selecting
the catalog version. Attachment rejects parent/child collisions before writes,
including attempts to add the old `rtl-dv-context` alias alongside a canonical
`rtl-dv-kit` owner. A legacy-only manifest remains supported.
Relative links are preferred; Windows cross-drive installs use absolute links
and must be reattached if the shared installation moves.

Read-only guidance is not a filesystem sandbox. A link inherits the shared
target's OS permissions; an administrator must make shared releases read-only
to consuming users. A writable development submodule can still be edited through
its links. Review its Git diff and change the kit deliberately, not via a project
skill path. Attachment itself does not chmod the shared installation.

The framework uses the existing hw/rtl, hw/dv and hw/pd layout conventions. For a
different layout, select overrides for affected roles/rules and supply actual paths
through the project profile; it does not guess source roots or execution targets.
Set `.claude/soc-lsp.json` with `bazel_target = //package:target` (JSON string value)
and optionally `verible_path`. The legacy tool name `configure_sys_tb_index` now
uses that explicit target, including its generated inventory/runfiles filenames.
Reconnect soc-lsp after changing its project configuration.
Do not replace the project scheduler or licensed execution policy with kit defaults.

Shared scripts resolve `PROJ_DIR` or the nearest project profile from the current
directory rather than treating the kit's directory as the project. Run them from
the consumer checkout. Native entrypoints remain at the same `.claude` paths.

The shared task branch and worktree helpers also live under `.claude/scripts`.
They use `codex/` branches and `CODEX_WORKTREE_ROOT` by default. A consumer can
set project-specific values in `.claude/task-worktree.env`, for example:

```sh
CLAUDE_KIT_TASK_BRANCH_PREFIX=claude
CLAUDE_KIT_WORKTREE_ROOT="${CLAUDE_WORKTREE_ROOT:-${TMPDIR:-/tmp}/claude_code_tasks}"
```

The helpers source this project-owned file from the selected checkout. Existing
`scripts/prepare_task_*.sh` entrypoints can forward to the shared helpers during
migration. `sync_local_configs.sh` keeps the SoC local-file whitelist and accepts
`CLAUDE_KIT_LOCAL_CONFIG_ROOT` or `claudeKit.localConfigRoot`; the older
`VIBE_SOC_LOCAL_CONFIG_ROOT` and `vibeSoc.localConfigRoot` remain supported.

Moving a file into the kit does not itself reduce token usage. Scoped loading,
selected context, bounded evidence, and the prompt budget remain in effect. Budget
checks expand the entrypoint's standalone local @imports and count linked rules.
Verify loaded instructions in the installed Claude Code client; static attachment
and fixture tests do not prove native discovery or simulator signoff.
