"""Non-destructive project attachment to a shared, versioned kit installation."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .core import KitError, discover_profile, resource_root, role_catalog, skill_catalog


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


def attach_project(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Serialize attachments; dry-run remains entirely read-only."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise KitError("Project root must be a directory")
    if dry_run:
        return _attach_project(root, dry_run=True)
    lock = root / ".claude-kit-attach.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise KitError("Another attachment or stale .claude-kit-attach.lock exists; inspect it before retrying") from exc
    os.close(descriptor)
    try:
        return _attach_project(root)
    finally:
        lock.unlink()


def _attach_project(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Link kit skills, expose native role wrappers, and add only its MCP entry.

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
    resources = resource_root().resolve(strict=True)
    desired: dict[str, tuple[str, str]] = {}
    for entry in skill_catalog():
        source = (resources / entry["path"]).parent.resolve(strict=True)
        if not source.is_relative_to(resources / "skills"):
            raise KitError(f"Skill escapes kit resources: {entry['id']}")
        relative = f".claude/skills/{entry['id']}"
        destination = _checked_target(root, relative)
        try:
            link_target = os.path.relpath(source, destination.parent)
        except ValueError:
            # Windows installations and projects may live on different drives.
            link_target = str(source)
        desired[relative] = ("link", link_target)
    for entry in role_catalog():
        source = (resources / entry["path"]).resolve(strict=True)
        if not source.is_file() or not source.is_relative_to(resources / "roles"):
            raise KitError(f"Role escapes kit resources: {entry['id']}")
        relative = f".claude/agents/kit-{entry['id']}.md"
        description = entry.get("summary") or f"Apply the {entry['id']} RTL/DV role to a project task."
        tools_line = "tools: Read, Glob, Grep\n" if entry["id"] in {"reviewer", "evidence-reviewer"} else ""
        body = f'''---
name: kit-{entry['id']}
description: {json.dumps(description)}
{tools_line}\
---

Read `{source.as_posix()}` for this role's process and completion criteria.
Read the project's CLAUDE.md and discovered project profile for scope,
permissions, tool routing and target/test facts. Shared kit resources are
read-only; keep project-specific changes in the project. Use registered MCP
tools for configured checks and report missing prerequisites as unverified.
'''
        desired[relative] = ("text", body)
    profile_path = discover_profile(root)
    if profile_path is None:
        profile_path = root / ".claude/project.toml"
        desired[".claude/project.toml"] = ("text", _profile(root.name))
    profile_relative = profile_path.relative_to(root).as_posix()
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
    expected_server = {"type": "stdio", "command": "claude-kit", "args": ["mcp", "serve", "--project-root", ".", "--profile", profile_relative]}
    existing_server = servers.get("claude-kit")
    if existing_server is not None and existing_server != expected_server:
        raise KitError("Existing claude-kit MCP definition differs; review and migrate that entry explicitly")
    if existing_server is None:
        servers["claude-kit"] = expected_server
        desired[".mcp.json"] = ("merge", _json(config))
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
            can_refresh = kind != "merge" and state["managed"].get(relative) == current and current is not None
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
    result = {"status": "planned" if dry_run else "passed", "project_root": str(root), "profile": profile_relative,
              "changed": sorted(changes), "skills": [item["id"] for item in skill_catalog()],
              "retired_managed_paths": retired, "functional_validation": "not_run"}
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
            previous = ("link", os.readlink(path)) if path.is_symlink() else (("bytes", path.read_bytes(), path.stat().st_mode & 0o7777) if path.exists() else None)
            fd, temporary = tempfile.mkstemp(prefix=".kit-", dir=path.parent)
            os.close(fd)
            tmp = Path(temporary)
            try:
                if kind == "link":
                    tmp.unlink()
                    tmp.symlink_to(value, target_is_directory=True)
                else:
                    tmp.write_text(value, encoding="utf-8", newline="\n")
                    if path.is_file() and not path.is_symlink():
                        tmp.chmod(path.stat().st_mode & 0o7777)
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
    except OSError as exc:
        for path, previous in reversed(backups):
            if path.exists() or path.is_symlink():
                path.unlink()
            if previous is not None:
                if previous[0] == "link":
                    path.symlink_to(previous[1], target_is_directory=True)
                else:
                    path.write_bytes(previous[1])
                    path.chmod(previous[2])
        for directory in reversed(created_dirs):
            directory.rmdir()
        raise KitError(f"Attachment failed and was rolled back: {exc}") from exc
    return result
