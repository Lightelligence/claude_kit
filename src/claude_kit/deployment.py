"""Non-destructive project attachment to a shared, versioned kit installation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from .core import SKILL_ALIASES, KitError, discover_profile, resource_root, role_catalog, skill_catalog


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _checked_target(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise KitError(f"Invalid attachment path: {relative}")
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)() or (parent.exists() and not parent.is_dir()):
            raise KitError(f"Attachment parent is not a real directory: {parent}")
    if not path.parent.resolve().is_relative_to(root):
        raise KitError(f"Attachment parent escapes project root: {relative}")
    return path


def _fingerprint(path: Path) -> str | None:
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if path.is_file():
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return "directory" if path.exists() else None


def _profile(project_id: str) -> str:
    # Known facts only; permissions start read-only until the project configures them.
    return f'''schema_version = 1
packs = ["common"]

[project]
id = {json.dumps(project_id)}
root = "."
language = "systemverilog"
platform = "linux"

[build]
system = "project-configured"
[build.commands]

[permissions]
writable = []
deletable = []
read_only = ["hw/**", "rtl/**", "dv/**", "tb/**", "docs/**", ".claude/**"]
forbidden = [".git/**", "secrets/**"]

[policies]
require_evidence = true
auto_commit = false
auto_push = false
'''


def _manifest_path(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    path = candidate if candidate.is_absolute() else root / candidate
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise KitError(f"Attachment manifest does not exist: {value}") from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise KitError(f"Attachment manifest must be a file inside the project root: {value}")
    return resolved


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise KitError(f"Attachment manifest {label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise KitError(f"Attachment manifest {label} contains duplicates")
    return value


_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _portable_name(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is None
        or value.endswith((".", " "))
        or value.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
    ):
        raise KitError(f"Invalid {label}: {value!r}")
    return value.casefold()


def _aliases(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise KitError(f"Attachment manifest aliases.{label} must be a table")
    aliases: dict[str, str] = {}
    normalized: set[str] = set()
    for name, resource_id in value.items():
        portable = _portable_name(name, "attachment alias name")
        if portable in normalized:
            raise KitError(f"Duplicate attachment alias name: {name}")
        if not isinstance(resource_id, str) or not resource_id:
            raise KitError(f"Attachment alias {name} must name a non-empty resource ID")
        aliases[name] = resource_id
        normalized.add(portable)
    return aliases


def _catalog_by_id(entries: list[dict[str, str]], kind: str) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    normalized: set[str] = set()
    for entry in entries:
        resource_id = entry["id"]
        portable = _portable_name(resource_id, f"{kind} ID in kit resources")
        if portable in normalized:
            raise KitError(f"Duplicate {kind} ID in kit resources: {resource_id}")
        catalog[resource_id] = entry
        normalized.add(portable)
    return catalog


def _reject_duplicate_targets(names: list[str], prefix: str) -> None:
    normalized: dict[str, str] = {}
    for name in names:
        portable = _portable_name(name, "attachment target name")
        if portable in normalized:
            raise KitError(f"Duplicate attachment target: {prefix}/{name}")
        normalized[portable] = name


def _validate_resource_tree(source: Path, boundary: Path, label: str) -> None:
    """Reject broken links and entries that resolve outside a resource boundary."""
    try:
        resolved_boundary = boundary.resolve(strict=True)
        entries = (source, *source.rglob("*"))
        for entry in entries:
            if not entry.resolve(strict=True).is_relative_to(resolved_boundary):
                raise KitError(f"{label} escapes kit resources")
    except (OSError, RuntimeError) as exc:
        raise KitError(f"Cannot validate {label.lower()} resources") from exc


def _load_manifest(root: Path, value: str | Path | None) -> dict[str, Any] | None:
    if value is None:
        return None
    path = _manifest_path(root, value)
    try:
        manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise KitError(f"Cannot read attachment manifest: {path.relative_to(root)}") from exc
    allowed = {"schema_version", "manage_profile", "manage_mcp", "kit_path", "roles", "skills", "aliases", "framework", "framework_exclude"}
    unknown = sorted(set(manifest) - allowed)
    if unknown:
        raise KitError(f"Unknown attachment manifest keys: {', '.join(unknown)}")
    if manifest.get("schema_version") != 1:
        raise KitError("Unsupported attachment manifest schema")
    for key in ("manage_profile", "manage_mcp"):
        if key in manifest and not isinstance(manifest[key], bool):
            raise KitError(f"Attachment manifest {key} must be a boolean")
    manifest["roles"] = _string_list(manifest.get("roles", []), "roles")
    manifest["skills"] = _string_list(manifest.get("skills", []), "skills")
    aliases = manifest.get("aliases", {})
    if not isinstance(aliases, dict) or set(aliases) - {"roles", "skills"}:
        raise KitError("Attachment manifest aliases may contain only roles and skills tables")
    manifest["aliases"] = {
        "roles": _aliases(aliases.get("roles", {}), "roles"),
        "skills": _aliases(aliases.get("skills", {}), "skills"),
    }
    if manifest.get("framework") not in (None, "soc"):
        raise KitError("Unknown framework; supported value is soc")
    manifest["framework_exclude"] = _string_list(manifest.get("framework_exclude", []), "framework_exclude")
    if manifest["framework_exclude"] and not manifest.get("framework"):
        raise KitError("framework_exclude requires a framework")
    kit_path = manifest.get("kit_path")
    if kit_path is not None:
        if not isinstance(kit_path, str) or not kit_path:
            raise KitError("Attachment manifest kit_path must be a non-empty project-relative path")
        kit_root = _checked_target(root, kit_path)
        try:
            kit_root = kit_root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise KitError(f"Vendored kit path does not exist: {kit_path}") from exc
        if not kit_root.is_relative_to(root) or not kit_root.is_dir():
            raise KitError(f"Vendored kit path must be a directory inside the project root: {kit_path}")
        resources = kit_root / "src/claude_kit/resources"
        try:
            resources = resources.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise KitError(f"Vendored kit resources do not exist: {kit_path}") from exc
        if not resources.is_relative_to(kit_root) or not resources.is_dir():
            raise KitError(f"Vendored kit resources escape the kit path: {kit_path}")
        manifest["resource_root"] = resources
    manifest["path"] = path.relative_to(root).as_posix()
    return manifest


def attach_project(
    root: Path, *, dry_run: bool = False, manifest: str | Path | None = None
) -> dict[str, Any]:
    """Serialize attachments; dry-run remains entirely read-only."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise KitError("Project root must be a directory")
    if dry_run:
        return _attach_project(root, dry_run=True, manifest=manifest)
    lock = root / ".claude-kit-attach.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise KitError("Another attachment or stale .claude-kit-attach.lock exists; inspect it before retrying") from exc
    try:
        return _attach_project(root, manifest=manifest)
    finally:
        owned = os.fstat(descriptor)
        os.close(descriptor)
        try:
            current = lock.lstat()
        except FileNotFoundError:
            current = None
        if (
            current is not None
            and not lock.is_symlink()
            and (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino)
        ):
            lock.unlink()


def _attach_project(
    root: Path, *, dry_run: bool = False, manifest: str | Path | None = None
) -> dict[str, Any]:
    """Link selected kit resources without replacing project-owned configuration.

    All conflicts are checked before writing. Reattachment updates only managed
    links/wrappers whose fingerprints still match. Project-specific files and
    MCP definitions are never force-overwritten.
    """
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise KitError("Project root must be a directory")
    state_relative = ".claude/kit-state.json"
    state_path = _checked_target(root, state_relative)
    if state_path.is_symlink():
        raise KitError("Attachment state must not be a symlink")
    state: dict[str, Any] = {"schema_version": 1, "managed": {}}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise KitError("Cannot read attachment state") from exc
        if not isinstance(state, dict) or state.get("schema_version") != 1 or not isinstance(state.get("managed"), dict):
            raise KitError("Unsupported attachment state")

    attachment = _load_manifest(root, manifest)
    resources = (
        attachment["resource_root"].resolve(strict=True)
        if attachment and "resource_root" in attachment
        else resource_root().resolve(strict=True)
    )
    if not resources.is_dir():
        raise KitError(f"Kit resource root does not exist: {resources}")
    role_entries = _catalog_by_id(role_catalog(resources), "role")
    skill_entries = _catalog_by_id(skill_catalog(resources), "skill")
    selected_roles = list(role_entries) if attachment is None else attachment["roles"]
    selected_skills = list(skill_entries) if attachment is None else attachment["skills"]
    role_aliases = {} if attachment is None else attachment["aliases"]["roles"]
    skill_aliases = {} if attachment is None else attachment["aliases"]["skills"]
    # Explicit legacy manifests keep their destination names. Fresh installs
    # advertise only canonical skills; do not introduce a duplicate by default.
    for old, canonical in SKILL_ALIASES.items():
        if canonical in skill_entries and old not in skill_entries:
            if old in selected_skills or old in skill_aliases.values():
                skill_entries[old] = skill_entries[canonical]
    alias_markers = {
        **{
            f".claude/agents/{name}.md": (
                f"<!-- claude-kit role-alias: {resource_id} -->"
            )
            for name, resource_id in role_aliases.items()
        },
        **{
            f".claude/skills/{name}/SKILL.md": (
                f"<!-- claude-kit skill-alias: {resource_id} -->"
            )
            for name, resource_id in skill_aliases.items()
        },
    }
    for resource_id in selected_roles + list(role_aliases.values()):
        if resource_id not in role_entries:
            raise KitError(f"Unknown role in attachment manifest: {resource_id}")
    for resource_id in selected_skills + list(skill_aliases.values()):
        if resource_id not in skill_entries:
            raise KitError(f"Unknown skill in attachment manifest: {resource_id}")

    desired: dict[str, tuple[str, str]] = {}

    def add_desired(relative: str, kind: str, value: str) -> None:
        _checked_target(root, relative)
        if relative in desired:
            raise KitError(f"Duplicate attachment target: {relative}")
        candidate = Path(relative.casefold())
        for existing in desired:
            other = Path(existing.casefold())
            if candidate == other or candidate in other.parents or other in candidate.parents:
                raise KitError(
                    f"Overlapping attachment targets: {existing} and {relative}; "
                    "select one owner or exclude the framework paths explicitly"
                )
        desired[relative] = (kind, value)

    if attachment and attachment.get("framework"):
        framework = (resources / "framework" / attachment["framework"]).resolve(strict=True)
        if not framework.is_relative_to(resources):
            raise KitError("Framework escapes kit resources")
        catalog = json.loads((framework / "manifest.json").read_text(encoding="utf-8"))
        files = _string_list(catalog.get("files"), "framework files")
        if catalog.get("schema_version") != 1 or len(files) != len(set(files)):
            raise KitError("Invalid framework manifest")
        excluded = set(attachment["framework_exclude"])
        if excluded - set(files):
            raise KitError("Unknown framework exclusion")
        for relative in files:
            if not relative.startswith(".claude/") or Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise KitError("Invalid framework attachment path")
            if relative in excluded:
                continue
            source = (framework / relative).resolve(strict=True)
            if not source.is_file() or not source.is_relative_to(framework):
                raise KitError("Framework file escapes resources or is missing")
            destination = _checked_target(root, relative)
            try:
                link_target = os.path.relpath(source, destination.parent)
            except ValueError:
                # Match catalog attachment behavior for Windows cross-drive installs.
                link_target = str(source)
            add_desired(relative, "link", link_target)

    skill_targets = [(item, item) for item in selected_skills] + list(skill_aliases.items())
    for old, canonical in SKILL_ALIASES.items():
        if old in selected_skills and canonical in skill_entries:
            canonical_prefix = f".claude/skills/{canonical}"
            if canonical in selected_skills or any(
                path == canonical_prefix or path.startswith(canonical_prefix + "/")
                for path in desired
            ):
                raise KitError(
                    f"Duplicate skill selection: {old} resolves to {canonical}; "
                    "select only the canonical skill or its framework owner"
                )
    _reject_duplicate_targets(
        [name for name, _ in skill_targets], ".claude/skills"
    )
    for name, resource_id in skill_targets:
        entry = skill_entries[resource_id]
        source = (resources / entry["path"]).parent.resolve(strict=True)
        skills_root = (resources / "skills").resolve(strict=True)
        if not source.is_dir() or not source.is_relative_to(skills_root):
            raise KitError(f"Skill escapes kit resources: {entry['id']}")
        _validate_resource_tree(source, skills_root, f"Skill {entry['id']}")
        if name == resource_id:
            relative = f".claude/skills/{name}"
            destination = _checked_target(root, relative)
            try:
                link_target = os.path.relpath(source, destination.parent)
            except ValueError:
                # Windows installations and projects may live on different drives.
                link_target = str(source)
            add_desired(relative, "link", link_target)
            continue
        relative = f".claude/skills/{name}/SKILL.md"
        alias_directory = _checked_target(root, f".claude/skills/{name}")
        if alias_directory.exists() and not alias_directory.is_symlink():
            if not alias_directory.is_dir():
                raise KitError(
                    "Existing project path conflicts with kit attachment: "
                    f".claude/skills/{name}"
                )
            entries = list(alias_directory.iterdir())
            if any(entry.name != "SKILL.md" for entry in entries):
                raise KitError(
                    "Existing project directory conflicts with kit attachment: "
                    f".claude/skills/{name}"
                )
        source_reference = (
            source.relative_to(root).as_posix()
            if source.is_relative_to(root)
            else source.as_posix()
        )
        description = entry.get("description") or (
            f"Apply the {resource_id} reusable skill under the {name} compatibility name."
        )
        body = f'''---
name: {json.dumps(name)}
description: {json.dumps(description)}
---

{alias_markers[relative]}
Read `{source_reference}/SKILL.md` and follow that skill's instructions.
Resolve any relative support-file references from `{source_reference}`.
'''
        add_desired(relative, "text", body)

    role_targets = [(f"kit-{item}", item) for item in selected_roles] + list(role_aliases.items())
    _reject_duplicate_targets(
        [name for name, _ in role_targets], ".claude/agents"
    )
    for name, resource_id in role_targets:
        entry = role_entries[resource_id]
        source = (resources / entry["path"]).resolve(strict=True)
        if not source.is_file() or not source.is_relative_to(resources / "roles"):
            raise KitError(f"Role escapes kit resources: {entry['id']}")
        relative = f".claude/agents/{name}.md"
        description = entry.get("summary") or f"Apply the {entry['id']} RTL/DV role to a project task."
        tools_line = "tools: Read, Glob, Grep\n" if entry["id"] in {"reviewer", "evidence-reviewer"} else ""
        source_reference = source.relative_to(root).as_posix() if source.is_relative_to(root) else source.as_posix()
        body = f'''---
name: {json.dumps(name)}
description: {json.dumps(description)}
{tools_line}\
---

{alias_markers.get(relative, "")}
Read `{source_reference}` for this role's process and completion criteria.
Read the project's CLAUDE.md and discovered project profile for scope,
permissions, tool routing and target/test facts. Shared kit resources are
read-only; keep project-specific changes in the project. Use registered MCP
tools for configured checks and report missing prerequisites as unverified.
'''
        add_desired(relative, "text", body)

    manage_profile = attachment is None or attachment.get("manage_profile", True)
    manage_mcp = attachment is None or attachment.get("manage_mcp", True)
    profile_path = discover_profile(root)
    if profile_path is None and manage_profile:
        profile_path = root / ".claude/project.toml"
        add_desired(".claude/project.toml", "text", _profile(root.name))
    profile_relative = profile_path.relative_to(root).as_posix() if profile_path else None

    original_config: bytes | None = None
    if manage_mcp:
        if profile_relative is None:
            raise KitError("MCP management requires an existing or managed project profile")
        config_path = _checked_target(root, ".mcp.json")
        if config_path.is_symlink():
            raise KitError("MCP configuration must not be a symlink")
        try:
            original_config = config_path.read_bytes() if config_path.exists() else None
            config = json.loads(original_config.decode("utf-8")) if original_config is not None else {}
        except (OSError, ValueError) as exc:
            raise KitError("Cannot read project MCP configuration") from exc
        if not isinstance(config, dict) or not isinstance(config.get("mcpServers", {}), dict):
            raise KitError("Project MCP configuration must contain an mcpServers object")
        servers = config.setdefault("mcpServers", {})
        if attachment is not None and "resource_root" in attachment:
            kit_root = attachment["resource_root"].parents[2]
            launcher = kit_root / "bin/claude-kit"
            try:
                resolved_launcher = launcher.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise KitError("Vendored MCP management requires bin/claude-kit") from exc
            if not resolved_launcher.is_file() or not resolved_launcher.is_relative_to(kit_root):
                raise KitError("Vendored MCP launcher escapes the kit path")
            expected_server = {
                "type": "stdio",
                "command": launcher.relative_to(root).as_posix(),
                "args": ["mcp", "serve", "--profile", profile_relative],
            }
            compatible_servers = (expected_server,)
        else:
            expected_server = {
                "type": "stdio",
                "command": "claude-kit",
                "args": ["mcp", "serve", "--profile", profile_relative],
            }
            legacy_server = {
                "type": "stdio",
                "command": "claude-kit",
                "args": [
                    "mcp",
                    "serve",
                    "--project-root",
                    ".",
                    "--profile",
                    profile_relative,
                ],
            }
            compatible_servers = (expected_server, legacy_server)
        existing_server = servers.get("claude-kit")
        if existing_server is not None and existing_server not in compatible_servers:
            raise KitError("Existing claude-kit MCP definition differs; review and migrate that entry explicitly")
        if existing_server is None:
            servers["claude-kit"] = expected_server
            add_desired(".mcp.json", "merge", _json(config))

    changes: dict[str, tuple[str, str]] = {}
    managed: dict[str, str] = {}
    before: dict[str, str | None] = {}
    for relative, (kind, value) in desired.items():
        path = _checked_target(root, relative)
        current = _fingerprint(path)
        if kind == "merge":
            parsed_fingerprint = "sha256:" + hashlib.sha256(original_config).hexdigest() if original_config is not None else None
            if current != parsed_fingerprint:
                raise KitError("MCP configuration changed during attachment planning")
        expected = "link:" + value if kind == "link" else "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
        if current != expected:
            marker = alias_markers.get(relative)
            marker_matches = False
            if marker is not None and path.is_file() and not path.is_symlink():
                try:
                    marker_matches = marker in path.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    marker_matches = False
            can_refresh = (
                kind != "merge"
                and state["managed"].get(relative) == current
                and current is not None
                and (marker is None or marker_matches)
            )
            if current is not None and kind != "merge" and not can_refresh:
                raise KitError(f"Existing project file conflicts with kit attachment: {relative}")
            changes[relative] = (kind, value)
            before[relative] = current
        if kind != "merge" and relative != ".claude/project.toml":
            managed[relative] = expected
    retired = sorted(set(state["managed"]) - set(managed))
    # Retain ownership evidence for retired resources until an explicit migration.
    managed.update({name: state["managed"][name] for name in retired})
    state_content = _json({"schema_version": 1, "managed": managed})
    if not state_path.exists() or state_path.read_text(encoding="utf-8") != state_content:
        changes[state_relative] = ("text", state_content)
        before[state_relative] = _fingerprint(state_path)
    result = {
        "status": "planned" if dry_run else "passed",
        "project_root": str(root),
        "profile": profile_relative,
        "manifest": attachment["path"] if attachment else None,
        "changed": sorted(changes),
        "skills": selected_skills,
        "roles": selected_roles,
        "retired_managed_paths": retired,
        "functional_validation": "not_run",
    }
    if dry_run:
        return result

    backups: list[tuple[Path, tuple[Any, ...] | None]] = []
    created_dirs: list[Path] = []
    try:
        for relative, (kind, value) in changes.items():
            path = _checked_target(root, relative)
            if _fingerprint(path) != before[relative]:
                raise OSError(f"Project changed during attachment: {relative}")
            missing = []
            parent = path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                parent.mkdir()
                created_dirs.append(parent)
            previous = (
                ("link", os.readlink(path))
                if path.is_symlink()
                else (("bytes", path.read_bytes(), path.stat().st_mode & 0o7777) if path.exists() else None)
            )
            fd, temporary = tempfile.mkstemp(prefix=".kit-", dir=path.parent)
            os.close(fd)
            tmp = Path(temporary)
            try:
                if kind == "link":
                    tmp.unlink()
                    tmp.symlink_to(value, target_is_directory=(path.parent / value).is_dir())
                else:
                    tmp.write_text(value, encoding="utf-8", newline="\n")
                    if path.is_file() and not path.is_symlink():
                        tmp.chmod(path.stat().st_mode & 0o7777)
                    elif os.name != "nt":
                        tmp.chmod(0o644)
                if _fingerprint(path) != before[relative]:
                    raise OSError(f"Project changed during attachment: {relative}")
                # Windows cannot replace an existing directory symlink with
                # another symlink using os.replace. Back up that exact link
                # before unlinking it; never unlink the directory it targets.
                unlinked = os.name == "nt" and path.is_symlink()
                if unlinked:
                    path.unlink()
                    backups.append((path, previous))
                os.replace(tmp, path)
                if not unlinked:
                    backups.append((path, previous))
            finally:
                if tmp.exists() or tmp.is_symlink():
                    tmp.unlink()
    except BaseException as exc:
        try:
            for path, previous in reversed(backups):
                if path.exists() or path.is_symlink():
                    path.unlink()
                if previous is not None:
                    if previous[0] == "link":
                        path.symlink_to(previous[1], target_is_directory=(path.parent / previous[1]).is_dir())
                    else:
                        path.write_bytes(previous[1])
                        path.chmod(previous[2])
            for directory in reversed(created_dirs):
                directory.rmdir()
        except OSError as rollback_exc:
            raise KitError(f"Attachment failed and rollback was incomplete: {rollback_exc}") from exc
        if isinstance(exc, OSError):
            raise KitError(f"Attachment failed and was rolled back: {exc}") from exc
        raise
    return result
