from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ToolProfileError(ValueError):
    """Raised when a project MCP tool-profile configuration is invalid."""


_SCHEMA_VERSION = 1
_MCP_CONFIG_NAME = ".mcp.json"
_PROFILE_CONFIG_NAME = ".claude/tool-profiles.json"
_PROFILE_DOCUMENT_FIELDS = frozenset({"schema_version", "profiles", "mcp_config"})
_PROFILE_FIELDS = frozenset({"description", "servers"})


class _DuplicateKeyError(ValueError):
    pass


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError(key)
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value}")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except _DuplicateKeyError as exc:
        raise ToolProfileError(f"{label} contains a duplicate field: {exc}") from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ToolProfileError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ToolProfileError(f"{label} must contain an object")
    return value


def _project_root(root: Path) -> Path:
    try:
        resolved = Path(root).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ToolProfileError(f"Project root cannot be resolved: {root}") from exc
    if not resolved.is_dir():
        raise ToolProfileError(f"Project root is not a directory: {root}")
    return resolved


def _safe_project_file(root: Path, relative: str, label: str) -> Path:
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ToolProfileError(f"{label} cannot be resolved: {candidate}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ToolProfileError(f"{label} resolves outside the project root: {candidate}") from exc
    if candidate.is_symlink():
        raise ToolProfileError(f"{label} must not be a symlink: {candidate}")
    if not resolved.is_file():
        raise ToolProfileError(f"{label} is not a regular file: {candidate}")
    return resolved


def _reject_unknown_fields(value: dict[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(key for key in value if key not in allowed)
    if unknown:
        raise ToolProfileError(f"{label} contains unknown field(s): {', '.join(unknown)}")


def _require_fields(value: dict[str, Any], required: frozenset[str], label: str) -> None:
    missing = sorted(key for key in required if key not in value)
    if missing:
        raise ToolProfileError(f"{label} is missing required field(s): {', '.join(missing)}")


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ToolProfileError(f"{label} must be a string")
    if not value or not value.strip() or "\x00" in value:
        raise ToolProfileError(f"{label} must be a non-empty name")
    return value


def _load_mcp_servers(root: Path, filename: str = _MCP_CONFIG_NAME) -> dict[str, dict[str, Any]]:
    path = _safe_project_file(root, filename, "Project MCP configuration")
    config = _read_json(path, "Project MCP configuration")
    _reject_unknown_fields(config, frozenset({"mcpServers"}), "Project MCP configuration")
    if "mcpServers" not in config:
        raise ToolProfileError("Project MCP configuration is missing required field: mcpServers")
    servers = config["mcpServers"]
    if not isinstance(servers, dict):
        raise ToolProfileError("Project MCP configuration mcpServers must be an object")
    for server_name, server_config in servers.items():
        _name(server_name, "MCP server name")
        if not isinstance(server_config, dict):
            raise ToolProfileError(f"MCP server {server_name!r} must contain an object")
    return servers


def _load_profiles(root: Path, registered_servers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    path = _safe_project_file(root, _PROFILE_CONFIG_NAME, "Tool-profile configuration")
    document = _read_json(path, "Tool-profile configuration")
    _reject_unknown_fields(document, _PROFILE_DOCUMENT_FIELDS, "Tool-profile configuration")
    _require_fields(document, frozenset({"schema_version", "profiles"}), "Tool-profile configuration")
    if type(document["schema_version"]) is not int or document["schema_version"] != _SCHEMA_VERSION:
        raise ToolProfileError("Tool-profile configuration schema_version must be 1")
    profiles = document["profiles"]
    if not isinstance(profiles, dict):
        raise ToolProfileError("Tool-profile configuration profiles must be an object")

    validated: dict[str, dict[str, Any]] = {}
    for profile_name, profile in profiles.items():
        _name(profile_name, "Tool profile name")
        if not isinstance(profile, dict):
            raise ToolProfileError(f"Tool profile {profile_name!r} must contain an object")
        label = f"Tool profile {profile_name!r}"
        _reject_unknown_fields(profile, _PROFILE_FIELDS, label)
        _require_fields(profile, _PROFILE_FIELDS, label)
        description = profile["description"]
        if not isinstance(description, str):
            raise ToolProfileError(f"{label} description must be a string")
        servers = profile["servers"]
        if not isinstance(servers, list):
            raise ToolProfileError(f"{label} servers must be an array")
        if not servers:
            raise ToolProfileError(f"{label} servers must not be empty")

        validated_servers: list[str] = []
        seen: set[str] = set()
        for server_name in servers:
            server_name = _name(server_name, f"{label} server name")
            if server_name in seen:
                raise ToolProfileError(f"{label} contains duplicate server: {server_name}")
            if server_name not in registered_servers:
                raise ToolProfileError(f"{label} references unknown MCP server: {server_name}")
            seen.add(server_name)
            validated_servers.append(server_name)
        validated[profile_name] = {
            "description": description,
            "servers": validated_servers,
        }
    return validated


def _load_project_configuration(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    resolved_root = _project_root(root)
    document = _read_json(
        _safe_project_file(resolved_root, _PROFILE_CONFIG_NAME, "Tool-profile configuration"),
        "Tool-profile configuration",
    )
    filename = _name(document.get("mcp_config", _MCP_CONFIG_NAME), "mcp_config")
    if Path(filename).is_absolute() or ".." in Path(filename).parts:
        raise ToolProfileError("mcp_config must be a project-relative path without traversal")
    servers = _load_mcp_servers(resolved_root, filename)
    profiles = _load_profiles(resolved_root, servers)
    return servers, profiles


def select_tool_profile(root: Path, name: str) -> dict[str, Any]:
    """Return the explicitly selected project MCP servers as an MCP config subset."""

    profile_name = _name(name, "Tool profile name")
    registered_servers, profiles = _load_project_configuration(root)
    if profile_name not in profiles:
        raise ToolProfileError(f"Unknown tool profile: {profile_name}")
    selected_names = profiles[profile_name]["servers"]
    return {
        "mcpServers": {
            server_name: registered_servers[server_name]
            for server_name in selected_names
        },
    }


def profile_catalog(root: Path) -> list[dict[str, Any]]:
    """Return profile metadata without exposing any MCP server configuration."""

    _, profiles = _load_project_configuration(root)
    return [
        {
            "name": profile_name,
            "description": profile["description"],
            "servers": list(profile["servers"]),
        }
        for profile_name, profile in profiles.items()
    ]
