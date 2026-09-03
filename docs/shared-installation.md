# Shared installation and project attachment

Use a version-pinned shared kit installation when several Claude Code projects
need the same roles, skills and protocol guidance. A site can provide that
installation through Environment Modules:

```sh
module add claude_kit/<approved-version>
claude-kit attach --project-root . --dry-run
claude-kit attach --project-root .
claude-kit doctor --strict
claude
```

Loading the module changes only shell environment variables. It does not
install packages, edit a checkout, start MCP processes, or launch EDA. Start
Claude Code from the project after loading the module so its MCP children
inherit the selected runtime. Explicit version selection keeps team upgrades
predictable; an administrator may provide an unversioned module default.

## Site administrator

Place a reviewed source release in a shared, read-only installation directory
and select a tested Python >=3.11 runtime. Run the following maintenance
command and install its stdout as the site's `claude_kit/<version>` modulefile:

```sh
python3 bin/claude-kit modulefile --kit-root /opt/dv/claude-kit/<version> --python /opt/dv/python/bin/python3
```

The generated Tcl sets `CLAUDE_KIT_ROOT`, `CLAUDE_KIT_PYTHON` and `PATH`.
The source checkout wrapper honors the interpreter selection before importing
the kit. No site path or license value is shipped in the generic package.
Make the release and its resources read-only to consuming users: resource
links intentionally point to the shared installation.

## Project owner

`attach` creates `.claude/project.toml` only if no supported profile already
exists. Add the project's actual build/test mapping and permissions there;
the initial profile grants no write access and invents no test target.
Existing `.ai` profiles remain supported and are not silently migrated.

The command links every built-in skill, including its supporting files, into
`.claude/skills`. Thin native `kit-*` agent definitions in `.claude/agents`
refer to the shared role documents. The reviewer wrappers expose only read
tools. It adds only the `claude-kit` entry in the root `.mcp.json`, preserving
every other server and setting. It does not change `.claude/settings.json`,
root `CLAUDE.md`, user-level MCPs, credentials or existing project skills.

Installation-local links, native wrappers and `.claude/kit-state.json` are
generated deployment state, not project facts. Keep those managed paths out
of project commits using the project's ignore policy. Keep the profile,
reviewed MCP configuration and actual project overrides version-controlled.
Module loading alone never activates a new set of resource links: run
`attach` again after switching the approved release.

Reattachment refreshes only unchanged, previously managed links/wrappers.
Conflicting project customizations cause a preflight error, before writing.
Run attachment in an idle checkout: its lock serializes kit attachers, not
unrelated editors. File contents and ordinary mode bits are preserved during
updates; custom ownership/ACL policies require site-specific validation.
Retired resources are reported for explicit review rather than deleted.
The existing `init` and `sync` commands retain their older copy-based behavior;
use `attach` for shared installations and do not use `sync --force` over links.

## Verification boundary

Attachment success means files and resource links were installed. It is not
evidence that all MCP tools, EDA flows, licenses or external services work.
Validate native discovery in the installed Claude Code version, MCP schemas,
safe functional fixtures and the selected licensed flows separately.

This feature does not bundle silicon-crew/vibe_soc source or deploy xverif,
drawio, Atlassian, simulator binaries or license settings. Preserve those
existing MCP definitions during migration. External code needs a verified
redistribution license before it can be included in a public kit release.
