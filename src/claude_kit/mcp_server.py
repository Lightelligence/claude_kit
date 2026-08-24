from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import (
    DEFAULT_ARTIFACT_MAX_BYTES,
    KitError,
    MAX_ARTIFACT_BYTES,
    inspect_project,
    load_profile,
    pack_catalog,
    read_artifact,
    redact_profile,
    review_evidence_file,
    resolve_context,
    role_catalog,
    command_menu,
    run_project_commands,
    run_project_command,
    skill_catalog,
    validate_profile,
    resolve_plan,
    workflow_catalog,
)


def _read_message() -> tuple[dict[str, Any] | None, str]:
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return None, "content-length"

    # The MCP Python SDK stdio transport uses one JSON-RPC object per line.
    # Keep accepting the older Content-Length framing for existing clients.
    if first_line.lstrip().startswith(b"{"):
        value = json.loads(first_line.decode("utf-8"))
        return (value if isinstance(value, dict) else None), "newline"

    headers: dict[str, str] = {}
    line = first_line
    while True:
        if line in (b"\n", b"\r\n"):
            break
        if b":" not in line:
            line = sys.stdin.buffer.readline()
            if not line:
                return None, "content-length"
            continue
        key, value = line.decode("ascii", errors="replace").split(":", 1)
        headers[key.strip().lower()] = value.strip()
        line = sys.stdin.buffer.readline()
        if not line:
            return None, "content-length"
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None, "content-length"
    payload = sys.stdin.buffer.read(length)
    if not payload:
        return None, "content-length"
    value = json.loads(payload.decode("utf-8"))
    return (value if isinstance(value, dict) else None), "content-length"


def _write_message(value: dict[str, Any], framing: str) -> None:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if framing == "newline":
        sys.stdout.buffer.write(payload + b"\n")
    else:
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
            "name": "list_skills",
            "description": "List reusable Claude Code RTL/DV skills.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_workflows",
            "description": "List reusable RTL/DV workflow plans and their routing hints.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "plan_task",
            "description": "Resolve a task into roles, skills, packs, project checks and evidence gates without executing commands.",
            "inputSchema": {
                "type": "object",
                "required": ["task"],
                "properties": {
                    "task": {"type": "string"},
                    "workflow": {"type": "string", "description": "Workflow id or auto"},
                    "roles": {"type": "array", "items": {"type": "string"}},
                    "packs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        {
            "name": "list_checks",
            "description": "List all profile-declared checks as an engineer-selectable menu with categories and approval requirements.",
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
                    "skills": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        {
            "name": "inspect_design",
            "description": "Return a read-only file and extension summary for configured project roots.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "read_artifact",
            "description": "Read a bounded UTF-8 project artifact without leaving the project root.",
            "inputSchema": {
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string"},
                    "max_bytes": {"type": "integer", "minimum": 0, "maximum": MAX_ARTIFACT_BYTES},
                },
            },
        },
        {
            "name": "review_evidence",
            "description": "Validate a project-relative evidence JSON file.",
            "inputSchema": {
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string"},
                    "strict": {"type": "boolean"},
                },
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
        tools.append({
            "name": "run_checks",
            "description": "Run an engineer-selected list of profile-declared checks sequentially and return per-check reports; confirm=true is required.",
            "inputSchema": {
                "type": "object",
                "required": ["names", "confirm"],
                "properties": {
                    "names": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "confirm": {"type": "boolean"},
                    "timeout": {"type": "integer", "minimum": 1},
                    "stop_on_error": {"type": "boolean"},
                },
            },
        })
    return tools


def _text_result(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, ensure_ascii=False)}]}


def _bool_argument(arguments: dict[str, Any], name: str, default: bool = False) -> bool:
    value = arguments.get(name, default)
    if not isinstance(value, bool):
        raise KitError(f"{name} must be a boolean")
    return value


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
    if name == "list_skills":
        return _text_result(skill_catalog())
    if name == "list_workflows":
        return _text_result(workflow_catalog())

    profile_path, profile = load_profile(root, explicit_profile)
    if name == "plan_task":
        task = arguments.get("task")
        if not isinstance(task, str):
            raise KitError("plan_task task must be a string")
        workflow = arguments.get("workflow", "auto")
        if not isinstance(workflow, str):
            raise KitError("plan_task workflow must be a string")
        return _text_result(resolve_plan(
            root,
            profile_path,
            profile,
            workflow,
            arguments.get("roles"),
            arguments.get("packs"),
            task,
        ))
    if name == "get_project_profile":
        issues = validate_profile(root, profile)
        return _text_result({
            "profile": str(profile_path.relative_to(root)),
            "project": redact_profile(profile),
            "validation": {
                "status": "failed" if any(item["level"] == "error" for item in issues) else "passed",
                "issues": issues,
            },
        })
    if name == "list_checks":
        return _text_result(command_menu(profile))
    if name == "resolve_context":
        task = arguments.get("task", "")
        if not isinstance(task, str):
            raise KitError("resolve_context task must be a string")
        context, manifest = resolve_context(
            root,
            profile_path,
            profile,
            arguments.get("roles"),
            arguments.get("packs"),
            task,
            arguments.get("skills"),
        )
        return _text_result({"context": context, "manifest": manifest})
    if name == "inspect_design":
        return _text_result(inspect_project(root, profile))
    if name == "read_artifact":
        path = arguments.get("path")
        if not isinstance(path, str):
            raise KitError("read_artifact requires path")
        max_bytes = arguments.get("max_bytes", DEFAULT_ARTIFACT_MAX_BYTES)
        return _text_result(read_artifact(root, path, max_bytes))
    if name == "review_evidence":
        path = arguments.get("path")
        if not isinstance(path, str):
            raise KitError("review_evidence requires path")
        return _text_result(review_evidence_file(root, profile, path, _bool_argument(arguments, "strict")))
    if name == "run_check":
        if not allow_exec:
            raise KitError("run_check is disabled; start the bridge with --allow-exec")
        if _bool_argument(arguments, "confirm") is not True:
            raise KitError("run_check requires confirm=true")
        name_value = arguments.get("name")
        if not isinstance(name_value, str):
            raise KitError("run_check requires a command name")
        return _text_result(run_project_command(root, profile, name_value, True))
    if name == "run_checks":
        if not allow_exec:
            raise KitError("run_checks is disabled; start the bridge with --allow-exec")
        if _bool_argument(arguments, "confirm") is not True:
            raise KitError("run_checks requires confirm=true")
        names = arguments.get("names")
        if not isinstance(names, list) or not all(isinstance(item, str) for item in names):
            raise KitError("run_checks requires names as an array of strings")
        timeout = arguments.get("timeout", 3600)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise KitError("run_checks timeout must be a positive integer")
        return _text_result(run_project_commands(
            root,
            profile,
            names,
            confirm=True,
            timeout=timeout,
            stop_on_error=_bool_argument(arguments, "stop_on_error"),
        ))
    raise KitError(f"Unknown tool: {name}")


def serve(root: Path, explicit_profile: str | None = None, allow_exec: bool = False) -> None:
    while True:
        request, framing = _read_message()
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
                if not isinstance(params, dict):
                    raise KitError("tools/call params must be an object")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise KitError("tools/call arguments must be an object")
                result = _call_tool(
                    str(params.get("name", "")),
                    arguments,
                    root,
                    explicit_profile,
                    allow_exec,
                )
            else:
                raise KitError(f"Unsupported method: {method}")
            if request_id is not None:
                _write_message({"jsonrpc": "2.0", "id": request_id, "result": result}, framing)
        except (KitError, OSError, ValueError, json.JSONDecodeError) as exc:
            if request_id is not None:
                _write_message({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(exc)},
                }, framing)
