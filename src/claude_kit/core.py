from __future__ import annotations

import fnmatch
import hashlib
import importlib.util
import inspect
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


def _project_path(root: Path, value: str | Path, label: str) -> Path:
    """Resolve a path and reject escaping or symlinked-outside paths."""
    if not isinstance(value, (str, Path)):
        raise KitError(f"{label} must be a project-relative path")
    if isinstance(value, str) and not value.strip():
        raise KitError(f"{label} must not be empty")
    project_root = root.resolve()
    candidate = Path(value)
    if ".." in candidate.parts:
        raise KitError(f"{label} must stay inside the project root: {value}")
    resolved = (candidate if candidate.is_absolute() else project_root / candidate).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise KitError(f"{label} resolves outside the project root: {value}") from exc
    return resolved


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
        return _project_path(root, explicit, "profile")
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
    normalized = lowered.replace("_", "").replace("-", "")
    if any(token in normalized for token in ("password", "secret", "token", "privatekey", "credential", "apikey", "accesskey")):
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
            try:
                path = _project_path(root, entry, f"roots.{group}")
            except KitError:
                add("error", f"roots.{group} escapes the project root: {entry}")
                continue
            if not path.exists():
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
            if not normalized.strip() or normalized.startswith("/") or ":" in normalized[:3] or ".." in Path(normalized).parts:
                add("error", f"permissions.{name} is not project-relative: {pattern}")

    for left_name, right_name in (("writable", "read_only"), ("writable", "forbidden"), ("read_only", "forbidden")):
        for left in permission_sets[left_name]:
            for right in permission_sets[right_name]:
                if _patterns_overlap(left, right):
                    add("error", f"permissions overlap: {left_name}:{left} and {right_name}:{right}")

    build = profile.get("build", {})
    if not isinstance(build, dict):
        add("error", "build must be an object")
        build = {}
    commands = build.get("commands", {}) if isinstance(build, dict) else {}
    if not isinstance(commands, dict):
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
        if not isinstance(cwd, str):
            add("error", f"build.commands.{name}.cwd must stay inside the project root")
        else:
            try:
                _project_path(root, cwd, f"build.commands.{name}.cwd")
            except KitError:
                add("error", f"build.commands.{name}.cwd must stay inside the project root")
        confirmation = command.get("confirmation")
        if confirmation is not None and confirmation not in ("required", "optional"):
            add("error", f"build.commands.{name}.confirmation must be required or optional")

    roles = profile.get("roles", {})
    if not isinstance(roles, (dict, list)):
        add("error", "roles must be an object or list")
        roles = {}
    try:
        role_defaults = roles.get("defaults", []) if isinstance(roles, dict) else roles
        role_ids = _as_list(role_defaults)
    except KitError:
        add("error", "roles.defaults must be a string or list of strings")
        role_ids = []
    known_roles = {item["id"] for item in role_catalog()}
    for identifier in role_ids:
        if identifier not in known_roles:
            add("error", f"Unknown role in profile defaults: {identifier}")

    packs = profile.get("packs", [])
    if not isinstance(packs, list) or not all(isinstance(item, str) and item for item in packs):
        add("error", "packs must be a list")
        packs = []
    known_packs = {item["id"] for item in pack_catalog()}
    for identifier in packs:
        if identifier not in known_packs:
            add("error", f"Unknown pack in profile: {identifier}")

    if "adapter" in profile:
        adapter = profile.get("adapter")
        if not isinstance(adapter, (str, dict)) or (isinstance(adapter, str) and not adapter.strip()):
            add("error", "adapter must be a non-empty path or object")
        else:
            adapter_value = adapter if isinstance(adapter, str) else adapter.get("path")
            if not isinstance(adapter_value, str) or not adapter_value.strip():
                add("error", "adapter.path is required")
            else:
                try:
                    _project_path(root, adapter_value, "adapter.path")
                except KitError:
                    add("error", f"adapter.path escapes the project root: {adapter_value}")
            if isinstance(adapter, dict):
                required = adapter.get("required_functions", [])
                if not isinstance(required, list) or not all(isinstance(item, str) and item for item in required):
                    add("error", "adapter.required_functions must be a list of non-empty strings")

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


def skill_catalog() -> list[dict[str, str]]:
    directory = resource_root() / "skills"
    result: list[dict[str, str]] = []
    for path in sorted(directory.rglob("SKILL.md")):
        metadata = _front_matter(path)
        result.append({
            "id": metadata.get("name", path.parent.name),
            "version": metadata.get("version", "1"),
            "description": metadata.get("description", ""),
            "path": str(path.relative_to(resource_root())).replace(os.sep, "/"),
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
    if not isinstance(task, str):
        raise KitError("task must be a string")
    role_config = profile.get("roles", {})
    defaults = role_config.get("defaults", []) if isinstance(role_config, dict) else role_config
    role_ids = _as_list(roles) if roles is not None else _as_list(defaults)
    pack_ids = _as_list(packs) if packs is not None else _as_list(profile.get("packs", []))
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
    root = root.resolve()
    groups = profile.get("roots", {}) if isinstance(profile, dict) else {}
    paths: list[tuple[str, Path]] = []
    if isinstance(groups, dict):
        for name, values in groups.items():
            for value in _as_list(values):
                paths.append((name, _project_path(root, value, f"roots.{name}")))
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


DEFAULT_ARTIFACT_MAX_BYTES = 100_000
MAX_ARTIFACT_BYTES = 1_000_000


def read_artifact(root: Path, relative_path: str, max_bytes: int = DEFAULT_ARTIFACT_MAX_BYTES) -> dict[str, Any]:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
        raise KitError("max_bytes must be a non-negative integer")
    if max_bytes > MAX_ARTIFACT_BYTES:
        raise KitError(f"max_bytes must not exceed {MAX_ARTIFACT_BYTES}")
    path = _project_path(root, relative_path, "artifact path")
    if not path.is_file():
        raise KitError(f"Artifact does not exist: {relative_path}")
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace")
    return {
        "path": path.relative_to(root.resolve()).as_posix(),
        "bytes": len(data),
        "truncated": truncated,
        "text": text,
    }


EVIDENCE_STATUSES = {"passed", "failed", "blocked", "skipped", "unknown"}


def _relative_project_path(root: Path, value: Any, field: str) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        path = _project_path(root, value, field)
    except KitError:
        return None
    return path.relative_to(root.resolve()).as_posix()


def _permission_match(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern.replace("\\", "/")) for pattern in patterns)


def validate_evidence(root: Path, profile: dict[str, Any], evidence: dict[str, Any], strict: bool = False) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(level: str, message: str) -> None:
        issues.append({"level": level, "message": message})

    if evidence.get("schema_version") != 1:
        add("error", "schema_version must be 1")
    project_id = profile.get("project", {}).get("id") if isinstance(profile.get("project"), dict) else None
    if evidence.get("project") != project_id:
        add("error", f"project must match profile project.id: {project_id}")
    if not isinstance(evidence.get("task"), str) or not evidence["task"].strip():
        add("error", "task is required")
    if evidence.get("source_revision") is not None and not isinstance(evidence.get("source_revision"), str):
        add("error", "source_revision must be a string")

    checks = evidence.get("checks", [])
    if not isinstance(checks, list):
        add("error", "checks must be a list")
        checks = []
    policies = profile.get("policies", {})
    if not isinstance(policies, dict):
        add("error", "policies must be an object")
        policies = {}
    require_evidence = bool(policies.get("require_evidence", False))
    if require_evidence and not checks:
        add("error", "checks must contain at least one check when policies.require_evidence is true")

    for index, check in enumerate(checks):
        prefix = f"checks[{index}]"
        if not isinstance(check, dict):
            add("error", f"{prefix} must be an object")
            continue
        if not isinstance(check.get("name"), str) or not check["name"].strip():
            add("error", f"{prefix}.name is required")
        if check.get("status") not in EVIDENCE_STATUSES:
            add("error", f"{prefix}.status must be one of {sorted(EVIDENCE_STATUSES)}")
        command = check.get("command")
        if command is not None and (not isinstance(command, list) or not all(isinstance(item, str) for item in command)):
            add("error", f"{prefix}.command must be a list of strings")
        if check.get("status") == "passed" and not command:
            add("warning", f"{prefix} is passed without command evidence")
        artifacts = check.get("artifacts", check.get("artifact", []))
        if isinstance(artifacts, str):
            artifacts = [artifacts]
        if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
            add("error", f"{prefix}.artifacts must be a string or list of strings")
            artifacts = []
        for artifact in artifacts:
            relative = _relative_project_path(root, artifact, f"{prefix}.artifacts")
            if relative is None:
                add("error", f"{prefix}.artifacts path is not project-relative: {artifact}")
            elif not (root / relative).is_file():
                add("warning", f"{prefix}.artifact does not exist: {relative}")

    permissions = profile.get("permissions", {})
    if not isinstance(permissions, dict):
        add("error", "permissions must be an object")
        permissions = {}
    writable_declared = "writable" in permissions
    try:
        writable = _as_list(permissions.get("writable", []))
        read_only = _as_list(permissions.get("read_only", []))
        forbidden = _as_list(permissions.get("forbidden", []))
    except KitError as exc:
        add("error", f"permissions are invalid: {exc}")
        writable, read_only, forbidden = [], [], []
    changes = evidence.get("changes", [])
    if not isinstance(changes, list):
        add("error", "changes must be a list")
        changes = []
    for index, change in enumerate(changes):
        if isinstance(change, str):
            path_value = change
        elif isinstance(change, dict):
            path_value = change.get("path")
        else:
            add("error", f"changes[{index}] must be a path or object")
            continue
        relative = _relative_project_path(root, path_value, f"changes[{index}]")
        if relative is None:
            add("error", f"changes[{index}] path is not project-relative: {path_value}")
        elif _permission_match(relative, forbidden) or _permission_match(relative, read_only):
            add("error", f"changes[{index}] is outside the writable scope: {relative}")
        elif writable_declared and not _permission_match(relative, writable):
            add("warning", f"changes[{index}] is not covered by permissions.writable: {relative}")

    for key in ("skipped", "risks"):
        value = evidence.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, (str, dict)) for item in value):
            add("error", f"{key} must be a list of strings or objects")

    if strict:
        for issue in issues:
            if issue["level"] == "warning":
                issue["level"] = "error"
    return issues


def review_evidence_file(root: Path, profile: dict[str, Any], relative_path: str, strict: bool = False) -> dict[str, Any]:
    artifact = read_artifact(root, relative_path, max_bytes=MAX_ARTIFACT_BYTES)
    try:
        evidence = json.loads(artifact["text"])
    except json.JSONDecodeError as exc:
        raise KitError(f"Evidence must be JSON: {relative_path}: {exc}") from exc
    if not isinstance(evidence, dict):
        raise KitError(f"Evidence must contain an object: {relative_path}")
    issues = validate_evidence(root, profile, evidence, strict)
    failed = any(item["level"] == "error" for item in issues)
    return {
        "status": "failed" if failed else "passed",
        "path": relative_path,
        "issues": issues,
        "evidence": _redact(evidence),
    }


def evidence_template() -> str:
    return (resource_root() / "templates" / "evidence.json").read_text(encoding="utf-8")


def _process_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_project_command(
    root: Path,
    profile: dict[str, Any],
    name: str,
    confirm: bool = False,
    timeout: int = 3600,
) -> dict[str, Any]:
    if not isinstance(name, str) or not name:
        raise KitError("Command name must be a non-empty string")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise KitError("timeout must be a positive integer")
    root = root.resolve()
    build = profile.get("build", {})
    commands = build.get("commands", {}) if isinstance(build, dict) else {}
    command = commands.get(name) if isinstance(commands, dict) else None
    if not isinstance(command, dict):
        raise KitError(f"Command is not declared in build.commands: {name}")
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise KitError(f"Invalid argv for command: {name}")
    confirmation = command.get("confirmation")
    if confirmation not in (None, "required", "optional"):
        raise KitError(f"Invalid confirmation policy for command: {name}")
    if confirmation == "required" and not confirm:
        raise KitError(f"Command {name} requires explicit confirmation (--confirm)")
    cwd_value = command.get("cwd", ".")
    cwd = _project_path(root, cwd_value, f"Command cwd for {name}")
    if not cwd.is_dir():
        raise KitError(f"Command cwd does not exist: {cwd_value}")
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "command": name,
            "argv": argv,
            "cwd": cwd.relative_to(root).as_posix(),
            "returncode": None,
            "stdout": _process_output(exc.stdout),
            "stderr": _process_output(exc.stderr),
            "timed_out": True,
            "timeout": timeout,
        }
    except OSError as exc:
        return {
            "status": "failed",
            "command": name,
            "argv": argv,
            "cwd": cwd.relative_to(root).as_posix(),
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "launch_error": True,
        }
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": name,
        "argv": argv,
        "cwd": cwd.relative_to(root).as_posix(),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def project_template(with_adapter: bool = False) -> str:
    content = (resource_root() / "templates" / "project.toml").read_text(encoding="utf-8")
    if with_adapter:
        content = content.replace(
            "# Optional project adapter:\n# [adapter]\n# path = \".ai/adapter.py\"\n# required_functions = [\"resolve_target\", \"resolve_test\"]",
            "[adapter]\npath = \".ai/adapter.py\"\nrequired_functions = [\"resolve_target\", \"resolve_test\", \"resolve_vip\", \"collect_artifacts\"]",
        )
    return content


def adapter_template() -> str:
    return (resource_root() / "templates" / "adapter.py").read_text(encoding="utf-8")


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


def mcp_config(kit_path: str) -> str:
    normalized_kit_path = str(kit_path).replace("\\", "/").rstrip("/")
    config = {
        "mcpServers": {
            "claude-kit": {
                "type": "stdio",
                "command": "python",
                "args": [
                    f"{normalized_kit_path}/bin/claude-kit",
                    "mcp",
                    "serve",
                    "--project-root",
                    ".",
                    "--profile",
                    ".ai/project.toml",
                ],
            }
        }
    }
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def adapter_path(root: Path, profile: dict[str, Any]) -> Path | None:
    if "adapter" not in profile:
        return None
    config = profile["adapter"]
    if isinstance(config, str):
        value = config
    elif isinstance(config, dict):
        value = config.get("path")
    else:
        raise KitError("adapter must be a path or object with path")
    if not isinstance(value, str) or not value.strip():
        raise KitError("adapter.path is required")
    return _project_path(root, value, "adapter.path")


def check_adapter(root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    path = adapter_path(root, profile)
    if path is None:
        return {"status": "skipped", "adapter": None, "functions": [], "signatures": {}, "issues": [{"level": "info", "message": "No adapter configured"}]}
    if not path.is_file():
        return {"status": "failed", "adapter": str(path.relative_to(root)), "functions": [], "signatures": {}, "issues": [{"level": "error", "message": "Adapter file does not exist"}]}
    spec = importlib.util.spec_from_file_location("claude_kit_project_adapter", path)
    if spec is None or spec.loader is None:
        return {"status": "failed", "adapter": str(path.relative_to(root)), "functions": [], "signatures": {}, "issues": [{"level": "error", "message": "Cannot load adapter module"}]}
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (Exception, SystemExit) as exc:  # Adapter code is project-owned and may import project tooling.
        return {"status": "failed", "adapter": str(path.relative_to(root)), "functions": [], "signatures": {}, "issues": [{"level": "error", "message": f"Adapter import failed: {exc}"}]}
    expected = ("resolve_target", "resolve_test", "resolve_vip", "collect_artifacts")
    config = profile.get("adapter")
    required = config.get("required_functions", []) if isinstance(config, dict) else []
    issues: list[dict[str, str]] = []
    signatures: dict[str, str] = {}
    if not isinstance(required, list) or not all(isinstance(name, str) and name for name in required):
        issues.append({"level": "error", "message": "adapter.required_functions must be a list of non-empty strings"})
        required = []
    names_to_check = list(expected)
    for name in required:
        if name not in names_to_check:
            names_to_check.append(name)
    provided = [name for name in names_to_check if callable(getattr(module, name, None))]
    issues.extend({"level": "error", "message": f"Missing required adapter function: {name}"} for name in required if name not in provided)
    for name in provided:
        function = getattr(module, name)
        try:
            signature = inspect.signature(function)
            signatures[name] = str(signature)
            accepts_argument = any(
                parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
                for parameter in signature.parameters.values()
            )
            if not accepts_argument:
                issues.append({"level": "error", "message": f"Adapter function {name} must accept at least one argument"})
        except (TypeError, ValueError) as exc:
            issues.append({"level": "error", "message": f"Cannot inspect adapter function {name}: {exc}"})
    if not provided:
        issues.append({"level": "warning", "message": "Adapter imports but provides no known contract functions"})
    return {
        "status": "failed" if any(item["level"] == "error" for item in issues) else "passed",
        "adapter": str(path.relative_to(root)),
        "functions": provided,
        "signatures": signatures,
        "issues": issues,
    }


def integration_skill() -> str:
    return (resource_root() / "templates" / "SKILL.md").read_text(encoding="utf-8")


def _skill_targets(root: Path) -> dict[Path, str]:
    targets = {root / ".claude" / "skills" / "rtl-dv-kit" / "SKILL.md": integration_skill()}
    resources = resource_root()
    for entry in skill_catalog():
        source = resources / entry["path"]
        targets[root / ".claude" / "skills" / entry["id"] / "SKILL.md"] = source.read_text(encoding="utf-8")
    return targets


def sync_project_skills(root: Path, force: bool = False) -> list[str]:
    created: list[str] = []
    for path, content in _skill_targets(root).items():
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        created.append(str(path.relative_to(root)).replace(os.sep, "/"))
    return created


def init_project(
    root: Path,
    kit_path: str = "third_party/claude_kit",
    force: bool = False,
    with_adapter: bool = False,
    with_mcp: bool = False,
    minimal: bool = False,
) -> list[str]:
    targets = {
        root / ".ai" / "project.toml": project_template(with_adapter),
        root / ".claude" / "CLAUDE.md": integration_claude(kit_path),
    }
    if with_adapter:
        targets[root / ".ai" / "adapter.py"] = adapter_template()
    if with_mcp:
        targets[root / ".mcp.json"] = mcp_config(kit_path)
    created: list[str] = []
    for path, content in targets.items():
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        created.append(str(path.relative_to(root)).replace(os.sep, "/"))
    skill_targets = _skill_targets(root)
    if minimal:
        integration_path = root / ".claude" / "skills" / "rtl-dv-kit" / "SKILL.md"
        skill_targets = {integration_path: integration_skill()}
    for path, content in skill_targets.items():
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        created.append(str(path.relative_to(root)).replace(os.sep, "/"))
    return created
