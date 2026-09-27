"""Read-only, project-scoped configuration inventory, never runtime discovery."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from .core import KitError, _front_matter
from .tool_profiles import (
    _load_mcp_servers, _load_project_configuration, _project_root,
    _read_json, _safe_project_file,
)

MAX_DOCUMENT_BYTES = 1_000_000
MAX_ENTRIES = 2000


def _bounded(path: Path) -> bytes:
    if not path.is_file():
        raise KitError("Audit input is not a regular file")
    with path.open("rb") as stream:
        content = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise KitError("Audit document exceeds 1 MB; narrow the input")
    return content


def _config(root: Path, relative: str) -> dict:
    path = _safe_project_file(root, relative, "Audit configuration")
    _bounded(path)
    return _read_json(path, "Audit configuration")


def _groups(entries: dict[str, Any]) -> list[list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for name, value in entries.items():
        # No configuration values or fingerprints leave this function.
        grouped[json.dumps(value, sort_keys=True, separators=(",", ":"))].append(name)
    return [sorted(names) for names in grouped.values() if len(names) > 1]


def _documents(root: Path, directory: str, *, skills: bool = False) -> tuple[list[dict], dict[str, str]]:
    base = root / directory
    if not base.exists() and not base.is_symlink():
        return [], {}
    if not base.is_dir():
        raise KitError(f"Audit directory is missing or not a directory: {directory}")
    # Project attachment deliberately uses links to shared skills. Inspect only
    # the declared entrypoint, never traverse an external resource tree.
    candidates = base.iterdir() if skills else base.rglob("*.md")
    records = []
    hashes = {}
    for index, entry in enumerate(candidates):
        if index >= MAX_ENTRIES:
            raise KitError(f"Audit exceeds {MAX_ENTRIES} entries: {directory}")
        path = entry / "SKILL.md" if skills and entry.is_dir() else entry
        relative = path.relative_to(root).as_posix()
        if skills and not entry.is_dir():
            if not entry.is_symlink():
                continue
        if not path.is_file():
            records.append({"path": relative, "status": "missing_entrypoint"})
            continue
        data = _bounded(path)
        record = {"path": relative, "status": "present", "bytes": len(data),
                  "linked": entry.is_symlink() or path.is_symlink() or base.is_symlink()}
        if skills:
            metadata = _front_matter(path)
            record["name"] = metadata.get("name", entry.name)
            record["description_bytes"] = len(metadata.get("description", "").encode("utf-8"))
            record["manual_only_declared"] = metadata.get("disable-model-invocation", "false").lower() == "true"
        records.append(record)
        hashes[relative] = hashlib.sha256(data).hexdigest()
    return sorted(records, key=lambda record: record["path"]), hashes


def audit_project(root: Path, selected: str | None = None) -> dict:
    root = _project_root(root)
    default_path = root / ".mcp.json"
    profile_path = root / ".claude/tool-profiles.json"
    defaults = {}
    if default_path.exists() or default_path.is_symlink():
        _config(root, ".mcp.json")
        defaults = _load_mcp_servers(root)
    catalog = defaults
    profiles = {}
    if profile_path.exists() or profile_path.is_symlink():
        document = _config(root, ".claude/tool-profiles.json")
        # Validate before resolving the potentially external catalog name.
        filename = document.get("mcp_config", ".mcp.json")
        if not isinstance(filename, str) or Path(filename).is_absolute() or ".." in Path(filename).parts:
            raise KitError("mcp_config must name a project-relative file")
        _config(root, filename)
        catalog, profiles = _load_project_configuration(root)
    if selected is not None and selected not in profiles:
        raise KitError(f"Unknown tool profile: {selected}")
    selection = list(defaults) if selected is None else profiles[selected]["servers"]
    findings = []
    default_only = sorted(set(defaults) - set(catalog))
    drift = sorted(name for name in defaults.keys() & catalog.keys() if defaults[name] != catalog[name])
    if default_only:
        findings.append({"code": "default_missing_from_catalog", "names": default_only})
    if drift:
        findings.append({"code": "default_catalog_drift", "names": drift})
    for names in _groups(catalog):
        findings.append({"code": "identical_server_definitions", "names": names})
    if catalog and not profiles:
        findings.append({"code": "no_task_profiles", "recommendation": "Define small task subsets in tool-profiles.json."})
    servers = []
    for name in sorted(set(defaults) | set(catalog)):
        memberships = [p for p, value in profiles.items() if name in value["servers"]]
        servers.append({"name": name, "default_declared": name in defaults,
                        "selected": name in selection, "profiles": memberships,
                        "placement": "default" if name in defaults else "on_demand" if memberships else "unassigned"})
    skills, hashes = _documents(root, ".claude/skills", skills=True)
    rules, _ = _documents(root, ".claude/rules")
    agents, _ = _documents(root, ".claude/agents")
    for paths in _groups(hashes):
        findings.append({"code": "identical_skill_entrypoints", "paths": paths})
    names = {s["path"]: s["name"] for s in skills if "name" in s}
    for paths in _groups(names):
        findings.append({"code": "duplicate_skill_names", "paths": paths})
    for skill in skills:
        if skill["status"] != "present":
            findings.append({"code": "missing_skill_entrypoint", "path": skill["path"]})
    instructions = []
    for relative in ("CLAUDE.md", ".claude/CLAUDE.md"):
        path = root / relative
        if path.exists() or path.is_symlink():
            instructions.append({"path": relative, "bytes": len(_bounded(path))})
    plugin_declarations = []
    hook_events = []
    mcp_disable_declarations = []
    # These declarations may be overridden by managed/user/runtime state. Do not
    # infer the effective plugin set or read credentials from the user's home.
    for relative in (".claude/settings.json", ".claude/settings.local.json"):
        if not (root / relative).exists() and not (root / relative).is_symlink():
            continue
        settings = _config(root, relative)
        plugins = settings.get("enabledPlugins", {})
        if not isinstance(plugins, dict) or any(type(v) is not bool for v in plugins.values()):
            raise KitError(f"enabledPlugins must map names to booleans: {relative}")
        plugin_declarations.extend({"name": name, "enabled_declared": value, "source": relative}
                                   for name, value in sorted(plugins.items()))
        hooks = settings.get("hooks", {})
        if not isinstance(hooks, dict):
            raise KitError(f"hooks must be an object: {relative}")
        hook_events.extend({"event": event, "source": relative} for event in sorted(hooks))
        disabled = settings.get("disabledMcpjsonServers", [])
        if not isinstance(disabled, list) or any(not isinstance(name, str) for name in disabled):
            raise KitError(f"disabledMcpjsonServers must be a name list: {relative}")
        mcp_disable_declarations.extend({"name": name, "source": relative} for name in disabled)
    if plugin_declarations:
        findings.append({"code": "plugin_contents_uninspected", "recommendation":
                         "Check enabled plugin MCP/skill/hook contents for overlap with kit resources."})
    if mcp_disable_declarations:
        findings.append({"code": "mcp_disable_declarations_present", "recommendation":
                         "Verify selected servers in native /mcp; configuration selection is not runtime activation."})
    return {"schema_version": 1, "kind": "project-tool-audit", "runtime_verified": False,
            "project_root": str(root), "selected_profile": selected,
            "summary": {"default_servers_declared": len(defaults), "catalog_servers": len(catalog),
                        "selected_servers": len(selection), "skills_present": sum(s["status"] == "present" for s in skills),
                        "skill_entrypoint_bytes": sum(s.get("bytes", 0) for s in skills),
                        "rules": len(rules), "agents": len(agents), "findings": len(findings)},
            "servers": servers, "profiles": [{"name": name, "servers": value["servers"]} for name, value in profiles.items()],
            "skills": skills, "rules": rules, "agents": agents, "instructions": instructions,
            "plugin_declarations": plugin_declarations, "hook_events": hook_events,
            "mcp_disable_declarations": mcp_disable_declarations, "findings": findings,
            "limitations": [
                "Static project files only; no MCP, EDA, hook or plugin code is executed.",
                "User/managed settings, CLI overrides, synced skills, legacy commands and plugin contents are not inspected.",
                "Configured does not mean loaded, connected, permitted or functionally verified.",
                "Document bytes are disk sizes, not tokens or measured context cost.",
                "Skill front matter uses kit's simple metadata parser, not Claude's runtime YAML parser.",
                "Identical entrypoints are duplicate candidates; supporting files and ownership need review before removal.",
            ]}


def render_audit(result: dict) -> str:
    def cell(value):
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    lines = ["# Project tool audit", "", "Static configuration only; runtime loading has not been verified.", "",
             "| MCP server | Placement | Selected | Profiles |", "| --- | --- | --- | --- |"]
    for server in result["servers"]:
        values = [server["name"], server["placement"], server["selected"], ", ".join(server["profiles"])]
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines.extend(["", "Summary: " + cell(json.dumps(result["summary"], ensure_ascii=False)), "", "Findings:"])
    lines.extend("- " + cell(json.dumps(f, ensure_ascii=False)) for f in result["findings"])
    lines.extend(["", "Project plugin declarations (not effective runtime state):"])
    lines.extend("- " + cell(json.dumps(p, ensure_ascii=False)) for p in result["plugin_declarations"])
    lines.extend(["", "| Skill entrypoint | Bytes | Manual-only declaration |", "| --- | --- | --- |"])
    for skill in result["skills"]:
        values = [skill["path"], skill.get("bytes", skill["status"]), skill.get("manual_only_declared", "unknown")]
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines.extend(["", *result["limitations"], ""])
    return "\n".join(lines)
