from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import (
    KitError,
    inspect_project,
    load_profile,
    pack_catalog,
    read_artifact,
    redact_profile,
    review_evidence_file,
    resolve_context,
    role_catalog,
    run_project_command,
)


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\n", b"\r\n"):
            break
        if b":" not in line:
            continue
        key, value = line.decode("ascii", errors="replace").split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    payload = sys.stdin.buffer.read(length)
    if not payload:
        return None
    value = json.loads(payload.decode("utf-8"))
    return value if isinstance(value, dict) else None


def _write_message(value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _tool_definitions(allow_exec: bool) -> list[dict[str, Any]]:
    tools = [
        {
            "name": "get_project_profile",
            "description": "Return the validated project profile.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_roles",
            "description": "List reusable RTL/DV roles.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_packs",
            "description": "List reusable protocol/VIP packs.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "resolve_context",
            "description": "Resolve a task context from the project profile, roles and packs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "roles": {"type": "array", "items": {"type": "string"}},
                    "packs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        {
            "name": "inspect_design",
            "description": "Return a read-only file and extension summary for configured project roots.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "review_evidence",
            "description": "Read a project-relative evidence or log artifact.",
            "inputSchema": {
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
        },
    ]
    if allow_exec:
        tools.append({
            "name": "run_check",
            "description": "Run a profile-declared command; explicit confirm=true is required.",
            "inputSchema": {
                "type": "object",
                "required": ["name", "confirm"],
                "properties": {
                    "name": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
            },
        })
    return tools


def _text_result(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, ensure_ascii=False)}]}


def _call_tool(
    name: str,
    arguments: dict[str, Any],
    root: Path,
    explicit_profile: str | None,
    allow_exec: bool,
) -> dict[str, Any]:
    if name == "list_roles":
        return _text_result(role_catalog())
    if name == "list_packs":
        return _text_result(pack_catalog())

    profile_path, profile = load_profile(root, explicit_profile)
    if name == "get_project_profile":
        return _text_result({"profile": str(profile_path.relative_to(root)), "project": redact_profile(profile)})
    if name == "resolve_context":
        context, manifest = resolve_context(
            root,
            profile_path,
            profile,
            arguments.get("roles"),
            arguments.get("packs"),
            str(arguments.get("task", "")),
        )
        return _text_result({"context": context, "manifest": manifest})
    if name == "inspect_design":
        return _text_result(inspect_project(root, profile))
    if name == "review_evidence":
        path = arguments.get("path")
        if not isinstance(path, str):
            raise KitError("review_evidence requires path")
        return _text_result(review_evidence_file(root, profile, path, bool(arguments.get("strict", False))))
    if name == "run_check":
        if not allow_exec:
            raise KitError("run_check is disabled; start the bridge with --allow-exec")
        if arguments.get("confirm") is not True:
            raise KitError("run_check requires confirm=true")
        return _text_result(run_project_command(root, profile, str(arguments.get("name", "")), True))
    raise KitError(f"Unknown tool: {name}")


def serve(root: Path, explicit_profile: str | None = None, allow_exec: bool = False) -> None:
    while True:
        request = _read_message()
        if request is None:
            return
        request_id = request.get("id")
        method = request.get("method")
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "claude-kit", "version": __version__},
                }
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                result = {"tools": _tool_definitions(allow_exec)}
            elif method == "tools/call":
                params = request.get("params") or {}
                result = _call_tool(
                    str(params.get("name", "")),
                    params.get("arguments") or {},
                    root,
                    explicit_profile,
                    allow_exec,
                )
            else:
                raise KitError(f"Unsupported method: {method}")
            if request_id is not None:
                _write_message({"jsonrpc": "2.0", "id": request_id, "result": result})
        except (KitError, OSError, ValueError, json.JSONDecodeError) as exc:
            if request_id is not None:
                _write_message({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(exc)},
                })
