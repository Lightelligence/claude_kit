#!/usr/bin/env python3
"""Generate or check the repository's Claude Code MCP config."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from framework_project import project_root
from typing import Any

ROOT = project_root()
MANIFEST = ROOT / ".claude/mcp-servers.json"
GENERIC_CONFIG = ROOT / ".mcp.json"
PROJECT_DIR_VARIABLE = "${CLAUDE_PROJECT_DIR}"
TRANSPORT_FIELDS = {"type", "command", "args", "cwd", "url", "headers"}


def validate_project_path(value: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty repository-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be a repository-relative path without '..'")
    normalized = path.as_posix()
    if normalized in ("", "."):
        raise ValueError(f"{field} must identify a path inside the repository")
    return normalized


def project_path(value: str, field: str) -> str:
    return f"{PROJECT_DIR_VARIABLE}/{validate_project_path(value, field)}"


def load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported MCP manifest schema_version")
    launcher = manifest.get("launcher")
    servers = manifest.get("servers")
    validate_project_path(launcher, "manifest launcher")
    if not isinstance(servers, list) or not servers:
        raise ValueError("manifest servers must be a non-empty list")

    names: set[str] = set()
    client_names: set[str] = set()
    for server in servers:
        if not isinstance(server, dict):
            raise ValueError("every manifest server must be an object")
        name = server.get("name")
        script = server.get("script")
        command = server.get("command")
        url = server.get("url")
        transport_keys = [key for key in ("script", "command", "url") if server.get(key) is not None]
        if not isinstance(name, str) or not name or name in names:
            raise ValueError(f"invalid or duplicate MCP server name: {name!r}")
        client_name = server.get("client_name")
        if client_name is not None and (not isinstance(client_name, str) or not client_name):
            raise ValueError(f"server {name}: client_name must be a non-empty string")
        if len(transport_keys) != 1:
            raise ValueError(f"server {name}: set exactly one of script, command, or url")
        if script is not None:
            validate_project_path(script, f"server {name} script")
        elif command is not None:
            if not isinstance(command, str) or not command:
                raise ValueError(f"server {name}: command must be a non-empty string")
            args = server.get("args", [])
            if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                raise ValueError(f"server {name}: args must be a list of strings")
            cwd = server.get("cwd")
            if cwd is not None:
                validate_project_path(cwd, f"server {name} cwd")
        else:
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError(f"server {name}: url must be an http(s) endpoint")
            headers = server.get("headers")
            if headers is not None:
                if not isinstance(headers, dict) or not all(
                        isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
                    raise ValueError(f"server {name}: headers must be a string-to-string object")
        for field in ("startup_timeout_sec", "tool_timeout_sec"):
            value = server.get(field)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"server {name}: {field} must be a positive integer")
        if not isinstance(server.get("default_enabled"), bool):
            raise ValueError(f"server {name}: default_enabled must be boolean")
        resolved_client_name = client_server_name(server, manifest.get("client_prefix", ""))
        if resolved_client_name in client_names:
            raise ValueError(f"duplicate MCP client name: {resolved_client_name!r}")
        names.add(name)
        client_names.add(resolved_client_name)
    return manifest


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def is_remote_server(server: dict[str, Any]) -> bool:
    return "url" in server


def client_server_name(server: dict[str, Any], prefix: str) -> str:
    """Return the explicit client name or derive one from transport and prefix."""
    if "client_name" in server:
        return server["client_name"]
    if is_remote_server(server):
        return server["name"]
    return f"{prefix}{server['name']}"


def render_claude_mcp_config(manifest: dict[str, Any]) -> str:
    prefix = manifest.get("client_prefix", "")
    launcher = manifest["launcher"]
    servers: dict[str, dict[str, Any]] = {}
    for server in manifest["servers"]:
        key = client_server_name(server, prefix)
        if is_remote_server(server):
            rendered: dict[str, Any] = {
                "type": "http",
                "url": server["url"],
            }
            if server.get("headers"):
                rendered["headers"] = server["headers"]
        elif "script" in server:
            rendered = {
                "type": "stdio",
                "command": "sh",
                "args": [
                    "-c",
                    f'repo_root=$(git rev-parse --show-toplevel) || exit; exec "$repo_root/{launcher}" "$repo_root/$1"',
                    "mcp-launcher",
                    server["script"],
                ],
            }
        else:
            rendered = {
                "type": "stdio",
                "command": server["command"],
                "args": server.get("args", []),
            }
            if "cwd" in server:
                rendered["cwd"] = project_path(server["cwd"], f"server {server['name']} cwd")
        servers[key] = rendered
    return json.dumps({"mcpServers": servers}, indent=2, ensure_ascii=False) + "\n"


def merge_generated_server(previous: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    """Replace canonical transport fields while preserving opaque server options."""
    preserved = {key: value for key, value in previous.items() if key not in TRANSPORT_FIELDS}
    return {**preserved, **generated}


def expected_configs() -> dict[Path, str]:
    manifest = load_manifest()
    generated = json.loads(render_claude_mcp_config(manifest))
    profiles_path = ROOT / ".claude/tool-profiles.json"
    profiles = json.loads(profiles_path.read_text(encoding="utf-8")) if profiles_path.is_file() else {}
    catalog_name = profiles.get("mcp_config")
    catalog = GENERIC_CONFIG
    if catalog_name is not None:
        if not isinstance(catalog_name, str) or not catalog_name or Path(catalog_name).is_absolute() or ".." in Path(catalog_name).parts:
            raise ValueError("mcp_config must be an in-project relative path")
        catalog = ROOT / catalog_name
        catalog.resolve().relative_to(ROOT.resolve())
        if catalog.is_symlink():
            raise ValueError("mcp_config must not be a symlink")
    source = catalog if catalog.is_file() else GENERIC_CONFIG
    existing = json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {}
    if not isinstance(existing, dict) or not isinstance(existing.get("mcpServers", {}), dict):
        raise ValueError("existing MCP configuration must contain an object")
    servers = existing.setdefault("mcpServers", {})
    # Preserve explicitly configured project servers and opaque options.
    if catalog != GENERIC_CONFIG and GENERIC_CONFIG.is_file():
        current = json.loads(GENERIC_CONFIG.read_text(encoding="utf-8"))
        for name, entry in current.get("mcpServers", {}).items():
            servers[name] = {**servers.get(name, {}), **entry}
    for name, entry in generated["mcpServers"].items():
        previous = servers.get(name, {})
        if not isinstance(previous, dict):
            raise ValueError("existing MCP server must be an object")
        servers[name] = merge_generated_server(previous, entry)
    outputs = {catalog: json.dumps(existing, indent=2, ensure_ascii=False) + "\n"}
    if catalog != GENERIC_CONFIG:
        selected = profiles.get("profiles", {}).get("default", {}).get("servers")
        if not isinstance(selected, list) or not selected or not all(isinstance(n, str) for n in selected):
            raise ValueError("split catalog requires a non-empty default tool profile")
        if len(set(selected)) != len(selected) or any(n not in servers for n in selected):
            raise ValueError("default profile contains duplicate or unknown servers")
        subset = {"mcpServers": {name: servers[name] for name in selected}}
        outputs[GENERIC_CONFIG] = json.dumps(subset, indent=2, ensure_ascii=False) + "\n"
    return outputs


def check() -> int:
    mismatches: list[Path] = []
    for path, expected in expected_configs().items():
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual != expected:
            mismatches.append(path)
    if mismatches:
        for path in mismatches:
            print(f"[MCP-CONFIG] OUT-OF-DATE: {path.relative_to(ROOT)}", file=sys.stderr)
        print("Run: python3 .claude/scripts/sync_mcp_configs.py --write", file=sys.stderr)
        return 2
    print("[MCP-CONFIG] Claude Code MCP config matches .claude/mcp-servers.json")
    return 0


def write() -> int:
    for path, content in expected_configs().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"[MCP-CONFIG] Wrote {path.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify configs (default)")
    mode.add_argument("--write", action="store_true", help="regenerate the Claude Code MCP config")
    args = parser.parse_args()
    try:
        return write() if args.write else check()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[MCP-CONFIG] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
