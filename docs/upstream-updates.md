# Taking vibe_soc updates

Maintainers stage an upstream update in the **kit**, validate it, then release a
new version. Projects keep their selected module version until they opt in.
Loading a module or starting an MCP never fetches upstream code.

## Update procedure

From a development checkout of claude_kit, use a new candidate directory:

```sh
claude-kit upstream stage --ref main --output /tmp/vibe-candidate
claude-kit upstream diff --candidate /tmp/vibe-candidate
claude-kit upstream apply --candidate /tmp/vibe-candidate
python3 -m unittest discover -s tests -q
```

`stage` uses Git partial fetching from the fixed upstream URL into a temporary
bare repository, then retrieves only the selected tool-source blobs in batches.
Automatic Git maintenance is disabled only in that disposable repository so a
detached writer cannot race temporary-directory cleanup. This does not change
the user's Git configuration or suppress cleanup errors.
Use Git >=2.31 for this network path. It records the resolved commit.
Use `--ref <commit>` for reproducibility, or
`--source /path/to/vibe_soc --ref origin/main` to use existing Git objects without
network access or changing that checkout. Dirty working-tree files are not
imported. The command never runs upstream hooks, setup scripts or MCPs.

Review the capability and dependency diff as well as the source diff. A static
Python decorator inventory detects many tool signature changes but is **not**
the runtime MCP schema. Node and external MCPs explicitly require a runtime
probe. New upstream servers are inventoried, not automatically enabled.
Manifest entries whose scripts are absent are reported as unavailable; their
presence in an imported catalog is not permission to activate them. For example,
revision `0b0ae368` lists `upf-gen`, `io-top-gen` and `noc-gen` without including
their implementations.

Before publishing an approved module release, run MCP initialize/list-tools and
safe functional fixtures in the supported Linux runtime. Compare runtime schemas
against the current deployment and run applicable licensed checks through the
project's execution adapter. Record untested dependencies as unverified, not
passed. Integrity checks and unit tests alone do not qualify an EDA release.

## Source and adaptation boundary

CRG adaptations preserve its top/CSV's register-qualified port contract and use
checked child processes with the active Python interpreter. Apply the parent
generator and register helper together. The helper delegates to the sibling
`yml2reg/scripts` data API, retaining interrupt/write-protection generation and
avoiding a second RTL implementation. Export/install both skills together.
Unsupported CRG AHB/DAB generation fails instead of emitting placeholder
functionality; this does not restrict standalone `yml2reg` protocols.

The reviewed Make filelist adaptation preserves the MCP argument contract:
explicit nonrecursive selection stays nonrecursive, and an omitted output returns
text without overwriting a working-directory filelist. The CLI's default output
remains unchanged. Apply both the wrapper and helper hunks together; a wrapper
that requests stdout from an older helper would instead create a file named `-`.

`src/claude_kit/resources/upstream/vibe_soc/source` is a byte-preserving snapshot.
Its adjacent `manifest.json` records provenance, commit, selected paths, Git
executable modes, SHA-256 digests and capability inventory. The selection contains
generic `.agents` resources and root `scripts`; chip/IP RTL, project targets,
credentials and unrelated repository trees are excluded. Templates may include
example HDL needed by the generic generators.

Keep kit launchers, compatibility fixes and project adapters **outside** this
snapshot. Submit generally useful fixes upstream where possible. Until accepted,
represent a necessary source change as an explicit reviewed patch in a separate
adapter layer, with an upstream revision and a regression test; do not hand-edit
the snapshot. The updater stops on local drift instead of discarding a fix.

The original upstream roles/rules retain their original project assumptions.
They are source material, not automatically active kit policy. Native Claude
resource exposure and project execution routing need explicit compatibility
validation. Existing consumer MCPs and skills remain authoritative until that
validation succeeds.

`apply` updates only the managed snapshot and uses a lock and rollback on rename
failure. Use an idle maintainer checkout; it does not lock unrelated editors.
It does not create a commit, push, merge, install packages, edit consumer MCP
settings, replace production modules or enable services. Roll back a published
kit by selecting the prior approved module version and reattaching its resources.

## Compatibility gates for the initial snapshot

### Export reviewed compatibility fixes

Maintainers can materialize the pinned source plus kit fixes in a **new**, idle
directory whose parent already exists:

```sh
claude-kit upstream check
claude-kit upstream export-adapted --output /tmp/vibe-adapted-review
```

On Windows, use an unused path such as `C:\Temp\vibe-adapted-review` instead.
This is a maintainer terminal command, not a required Claude prompt or extra MCP
call. It does not install dependencies, start servers, change project settings,
or automatically replace existing consumer files.

The export keeps the complete `source/` layout, including generator scripts,
catalogs, templates and shared runtime helpers. `adaptation.json` records the
upstream revision, patch digest and resulting file hashes; it is **not** a pristine
snapshot manifest and cannot be passed to `upstream apply`. Functional validation
remains `not_run` until the affected runtime has been tested separately.

Reviewed exact-context patches live in
`src/claude_kit/resources/adaptations/vibe_soc/patches.json`, outside the immutable
snapshot. They preserve the memory-wrapper capacity/port/interface fix,
the Make-only build skill's engineer-selected DV checks, and RTL integration
fixes for complete port parsing, parameterized wrappers and removed-module
mapping cleanup. Library-stub adaptations preserve numeric bus ranges and reject
unsupported types/dimensions instead of emitting incorrect pins. Each patch locks the
upstream commit and before/after SHA-256 hashes. There is no fuzzy application:
upstream changes require explicit review and rebasing, not a manifest rehash.
The exporter refuses existing destinations and links. An I/O failure may leave a
partial directory for inspection; only a completed export has `adaptation.json`.

Regression coverage: `tests/test_adaptations.py`, `tests/test_memwrap_capacity.py`,
`tests/test_integrate_contract.py`, `tests/test_lib_stub_ports.py`
and the CLI export test. Before adapting a consumer, compare its current files:
they can contain independent changes or an older upstream revision. Do not copy
an entire exported tree over a working project or rerun upstream configuration
synchronizers. Update only reviewed files through that project's normal Git/PR
workflow, then verify the registered MCP runtime.

Treat these as migrations, not automatic activation of the latest catalog:

- Preserve existing external and project-adapter MCP entries; upstream config
  synchronizers generate an upstream-specific server set and can drop additions.
- Preserve existing Loop state until its stage/contract migration is validated.
- Validate the newer memory-wrapper backend and added build RDC/DFT contracts.
- Provide and test the Node runtime before enabling WaveDrom. Python server
  connectivity does not establish that the Node backend is installed.
- Validate OpenROAD/PDK and other optional licensed/external dependencies on
  their own fixtures. Source presence is not backend availability.

## Notices

The repository owner confirmed authorization to redistribute vibe_soc-derived
content on 2026-09-03. The pinned upstream revision did not include a root
LICENSE file; this is not an assertion that upstream is MIT-licensed. Retain
upstream headers and provenance. The kit's own license does not relicense
third-party content; obtain applicable permission before redistributing it
outside the scope of that authorization. Future upstream LICENSE/COPYING/NOTICE
files are retained by the updater.
