from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Iterable


class KitError(Exception):
    """A user-facing configuration or execution error."""


PROFILE_NAMES = (
    ".ai/project.toml",
    ".claude-kit/project.toml",
    ".ai/project.json",
    ".claude-kit/project.json",
    "project.toml",
    "project.json",
)


def resource_root() -> Path:
    return Path(__file__).resolve().parent / "resources"


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise KitError("Expected a string or a list of strings")


def _load_document(path: Path) -> dict[str, Any]:
    try:
        if path.suffix.lower() == ".toml":
            with path.open("rb") as handle:
                value = tomllib.load(handle)
        elif path.suffix.lower() == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        else:
            raise KitError(f"Unsupported profile format: {path.suffix}")
    except (OSError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        raise KitError(f"Cannot read profile {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise KitError(f"Profile must contain an object: {path}")
    return value


def find_project_root(start: Path | None = None) -> Path:
    candidate = (start or Path.cwd()).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for path in (candidate, *candidate.parents):
        if (path / ".git").exists():
            return path
        if any((path / name).is_file() for name in PROFILE_NAMES):
            return path
    return candidate


def discover_profile(root: Path, explicit: str | Path | None = None) -> Path | None:
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = root / path
        return path.resolve()
    for name in PROFILE_NAMES:
        path = root / name
        if path.is_file():
            return path.resolve()
    return None


def load_profile(root: Path, explicit: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    path = discover_profile(root, explicit)
    if path is None:
        names = ", ".join(PROFILE_NAMES[:4])
        raise KitError(f"No project profile found below {root}. Expected one of: {names}")
    return path, _load_document(path)


def _pattern_prefix(pattern: str) -> str:
    value = pattern.replace("\\", "/").strip("/")
    for suffix in ("/**/*", "/**", "/*"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value.rstrip("/")


def _patterns_overlap(left: str, right: str) -> bool:
    if fnmatch.fnmatch(left, right) or fnmatch.fnmatch(right, left):
        return True
    a = _pattern_prefix(left)
    b = _pattern_prefix(right)
    return bool(a and b and (a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/")))


def _redact(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(token in lowered for token in ("password", "secret", "token", "private_key", "credential")):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    return value


def redact_profile(value: Any) -> Any:
    """Return a copy safe to expose in context, manifests or MCP responses."""
    return _redact(value)


def validate_profile(root: Path, profile: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(level: str, message: str) -> None:
        issues.append({"level": level, "message": message})

    version = profile.get("schema_version")
    if not isinstance(version, int):
        add("error", "schema_version must be an integer")
    elif version != 1:
        add("error", f"Unsupported schema_version: {version}")

    project = profile.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("id"), str) or not project["id"].strip():
        add("error", "project.id is required")

    roots = profile.get("roots", {})
    if not isinstance(roots, dict):
        add("error", "roots must be an object")
        roots = {}
    for group, values in roots.items():
        try:
            entries = _as_list(values)
        except KitError:
            add("error", f"roots.{group} must be a string or list of strings")
            continue
        for entry in entries:
            path = Path(entry)
            if path.is_absolute() or ".." in path.parts:
                add("error", f"roots.{group} escapes the project root: {entry}")
            elif not (root / path).exists():
                add("warning", f"roots.{group} does not exist yet: {entry}")

    permissions = profile.get("permissions", {})
    if not isinstance(permissions, dict):
        add("error", "permissions must be an object")
        permissions = {}
    permission_sets: dict[str, list[str]] = {}
    for name in ("writable", "read_only", "forbidden"):
        try:
            permission_sets[name] = _as_list(permissions.get(name, []))
        except KitError:
            add("error", f"permissions.{name} must be a string or list of strings")
            permission_sets[name] = []
        for pattern in permission_sets[name]:
            normalized = pattern.replace("\\", "/")
            if normalized.startswith("/") or ":" in normalized[:3] or ".." in Path(normalized).parts:
                add("error", f"permissions.{name} is not project-relative: {pattern}")

    for left_name, right_name in (("writable", "read_only"), ("writable", "forbidden"), ("read_only", "forbidden")):
        for left in permission_sets[left_name]:
            for right in permission_sets[right_name]:
                if _patterns_overlap(left, right):
                    add("error", f"permissions overlap: {left_name}:{left} and {right_name}:{right}")

    build = profile.get("build", {})
    if build and not isinstance(build, dict):
        add("error", "build must be an object")
        build = {}
    commands = build.get("commands", {}) if isinstance(build, dict) else {}
    if commands and not isinstance(commands, dict):
        add("error", "build.commands must be an object")
        commands = {}
    for name, command in commands.items():
        if not isinstance(command, dict):
            add("error", f"build.commands.{name} must be an object")
            continue
        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            add("error", f"build.commands.{name}.argv must be a non-empty list of strings")
        cwd = command.get("cwd", ".")
        if not isinstance(cwd, str) or Path(cwd).is_absolute() or ".." in Path(cwd).parts:
            add("error", f"build.commands.{name}.cwd must stay inside the project root")

    roles = profile.get("roles", {})
    if roles and not isinstance(roles, (dict, list)):
        add("error", "roles must be an object or list")
    packs = profile.get("packs", [])
    if packs and not isinstance(packs, list):
        add("error", "packs must be a list")

    return issues


def doctor(root: Path, explicit_profile: str | Path | None = None, strict: bool = False) -> dict[str, Any]:
    try:
        profile_path, profile = load_profile(root, explicit_profile)
    except KitError as exc:
        return {"status": "failed", "profile": None, "issues": [{"level": "error", "message": str(exc)}]}
    issues = validate_profile(root, profile)
    failed = any(item["level"] == "error" for item in issues) or (strict and any(item["level"] == "warning" for item in issues))
    return {
        "status": "failed" if failed else "passed",
        "profile": str(profile_path.relative_to(root)),
        "issues": issues,
    }


def _front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {"id": path.stem}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip("\"'")
    result.setdefault("id", path.stem)
    return result


def role_catalog() -> list[dict[str, str]]:
    directory = resource_root() / "roles"
    result: list[dict[str, str]] = []
    for path in sorted(directory.rglob("*.md")):
        metadata = _front_matter(path)
        title = next((line[2:].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("# ")), path.stem)
        result.append({
            "id": metadata["id"],
            "version": metadata.get("version", "1"),
            "scope": metadata.get("scope", "any"),
            "title": title,
            "path": str(path.relative_to(resource_root())).replace(os.sep, "/"),
        })
    return result


def pack_catalog() -> list[dict[str, Any]]:
    directory = resource_root() / "packs"
    result: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("pack.json")):
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KitError(f"Invalid pack metadata {path}: {exc}") from exc
        if not isinstance(metadata, dict) or not isinstance(metadata.get("id"), str):
            raise KitError(f"Pack metadata requires id: {path}")
        result.append({
            **metadata,
            "path": str(path.parent.relative_to(resource_root())).replace(os.sep, "/"),
        })
    return result


def _find_by_id(entries: Iterable[dict[str, Any]], identifier: str, kind: str) -> dict[str, Any]:
    entries = list(entries)
    for entry in entries:
        if entry.get("id") == identifier:
            return entry
    known = ", ".join(str(item.get("id")) for item in entries)
    raise KitError(f"Unknown {kind} {identifier}. Available: {known or '<none>'}")


def _source_entry(path: Path, display_root: Path) -> dict[str, str]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(display_root)).replace(os.sep, "/"),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def resolve_context(
    root: Path,
    profile_path: Path,
    profile: dict[str, Any],
    roles: list[str] | None,
    packs: list[str] | None,
    task: str,
) -> tuple[str, dict[str, Any]]:
    role_config = profile.get("roles", {})
    defaults = role_config.get("defaults", []) if isinstance(role_config, dict) else role_config
    role_ids = roles or _as_list(defaults)
    pack_ids = packs or _as_list(profile.get("packs", []))
    resources = resource_root()
    sources: list[dict[str, str]] = []
    sections: list[str] = []

    if not role_ids:
        sections.append("## Roles\n\nNo role selected.")
    else:
        sections.append("## Roles")
        for identifier in role_ids:
            entry = _find_by_id(role_catalog(), identifier, "role")
            path = resources / entry["path"]
            sources.append(_source_entry(path, resources))
            sections.append(f"\n### {identifier}\n\n{path.read_text(encoding='utf-8').strip()}\n")

    if not pack_ids:
        sections.append("## Packs\n\nNo protocol/VIP pack selected.")
    else:
        sections.append("## Packs")
        for identifier in pack_ids:
            entry = _find_by_id(pack_catalog(), identifier, "pack")
            pack_dir = resources / entry["path"]
            sources.append(_source_entry(pack_dir / "pack.json", resources))
            entrypoints = entry.get("entrypoints") or ["overview.md"]
            for relative in entrypoints:
                path = pack_dir / str(relative)
                if not path.is_file():
                    raise KitError(f"Pack {identifier} entrypoint does not exist: {relative}")
                sources.append(_source_entry(path, resources))
                sections.append(f"\n### {identifier}: {relative}\n\n{path.read_text(encoding='utf-8').strip()}\n")

    redacted_profile = _redact(profile)
    context = "\n".join([
        "# Claude Kit Resolved Context",
        "",
        f"Project: {profile.get('project', {}).get('id', '<unknown>')}",
        f"Profile: {profile_path.relative_to(root).as_posix()}",
        "",
        "## Task",
        "",
        task.strip() or "No task text supplied.",
        "",
        "## Project facts",
        "",
        "~~~json",
        json.dumps(redacted_profile, indent=2, ensure_ascii=False),
        "~~~",
        "",
        "\n".join(sections),
        "",
        "## Evidence contract",
        "",
        "- State which files changed and why.",
        "- List every check command that ran and its result.",
        "- Mark checks that were skipped or blocked.",
        "- Do not claim verification without execution evidence.",
        "",
    ])
    manifest = {
        "schema_version": 1,
        "project": profile.get("project", {}).get("id"),
        "profile": str(profile_path.relative_to(root)).replace(os.sep, "/"),
        "roles": role_ids,
        "packs": pack_ids,
        "task": task,
        "sources": sources,
        "warnings": [],
    }
    return context, manifest


def inspect_project(root: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    groups = profile.get("roots", {}) if isinstance(profile, dict) else {}
    paths: list[tuple[str, Path]] = []
    if isinstance(groups, dict):
        for name, values in groups.items():
            for value in _as_list(values):
                paths.append((name, root / value))
    if not paths:
        paths = [("project", root)]
    counts: dict[str, dict[str, Any]] = {}
    seen: set[Path] = set()
    scanned = 0
    truncated = False
    for group, directory in paths:
        record = counts.setdefault(group, {"path": str(directory.relative_to(root)), "files": 0, "extensions": {}})
        if not directory.exists():
            record["missing"] = True
            continue
        for path in directory.rglob("*"):
            if path.is_symlink() or not path.is_file() or ".git" in path.parts:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            scanned += 1
            if scanned > 20000:
                truncated = True
                break
            record["files"] += 1
            suffix = path.suffix.lower() or "<none>"
            record["extensions"][suffix] = record["extensions"].get(suffix, 0) + 1
        if truncated:
            break
    return {"root": str(root), "groups": counts, "scanned_files": min(scanned, 20000), "truncated": truncated}


def read_artifact(root: Path, relative_path: str, max_bytes: int = 100_000) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise KitError(f"Artifact path escapes project root: {relative_path}") from exc
    if not path.is_file():
        raise KitError(f"Artifact does not exist: {relative_path}")
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace")
    return {"path": relative_path, "bytes": len(data), "truncated": truncated, "text": text}


def run_project_command(
    root: Path,
    profile: dict[str, Any],
    name: str,
    confirm: bool = False,
    timeout: int = 3600,
) -> dict[str, Any]:
    build = profile.get("build", {})
    commands = build.get("commands", {}) if isinstance(build, dict) else {}
    command = commands.get(name) if isinstance(commands, dict) else None
    if not isinstance(command, dict):
        raise KitError(f"Command is not declared in build.commands: {name}")
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise KitError(f"Invalid argv for command: {name}")
    if command.get("confirmation") == "required" and not confirm:
        raise KitError(f"Command {name} requires explicit confirmation (--confirm)")
    cwd_value = command.get("cwd", ".")
    cwd = (root / cwd_value).resolve()
    try:
        cwd.relative_to(root.resolve())
    except ValueError as exc:
        raise KitError(f"Command cwd escapes project root: {cwd_value}") from exc
    if not cwd.is_dir():
        raise KitError(f"Command cwd does not exist: {cwd_value}")
    completed = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": name,
        "argv": argv,
        "cwd": str(cwd.relative_to(root)),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def project_template() -> str:
    return (resource_root() / "templates" / "project.toml").read_text(encoding="utf-8")


def integration_claude(kit_path: str) -> str:
    return f"""# Claude Kit integration

This project uses the reusable RTL/DV Claude kit.

- Read the project profile at .ai/project.toml before making changes.
- Use the repo-local CLI through the pinned kit path: {kit_path}.
- Keep changes inside the profile permissions.
- Prefer read-only inspect/context/log commands before editing.
- Record commands, results, skipped checks and unresolved risks.
- Do not claim verification without evidence.
- Do not modify vendor/generated files unless the profile explicitly allows it.

The kit's shared role and protocol guidance is available under:
{kit_path}/src/claude_kit/resources/
"""


def integration_skill() -> str:
    return (resource_root() / "templates" / "SKILL.md").read_text(encoding="utf-8")


def init_project(root: Path, kit_path: str = "third_party/claude_kit", force: bool = False) -> list[str]:
    targets = {
        root / ".ai" / "project.toml": project_template(),
        root / ".claude" / "CLAUDE.md": integration_claude(kit_path),
        root / ".claude" / "skills" / "rtl-dv-kit" / "SKILL.md": integration_skill(),
    }
    created: list[str] = []
    for path, content in targets.items():
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        created.append(str(path.relative_to(root)).replace(os.sep, "/"))
    return created
