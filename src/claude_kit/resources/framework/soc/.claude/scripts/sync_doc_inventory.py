#!/usr/bin/env python3
"""Generate or check bounded current-inventory blocks in Claude docs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from framework_project import project_root
from typing import Any

ROOT = project_root()
DOCS = ROOT / ".claude" / "docs"
SKILLS = ROOT / ".claude" / "skills"
AGENTS = ROOT / ".claude" / "agents"
KIT_RESOURCES = (
    ROOT / "third_party" / "claude_kit" / "src" / "claude_kit" / "resources"
)
CATALOG = ROOT / ".claude" / "mcp-catalog.json"
PROFILES = ROOT / ".claude" / "tool-profiles.json"

BEGIN = "<!-- BEGIN GENERATED CURRENT INVENTORY -->"
END = "<!-- END GENERATED CURRENT INVENTORY -->"
BLOCK_RE = re.compile(
    rf"{re.escape(BEGIN)}\n.*?{re.escape(END)}",
    flags=re.DOTALL,
)


def _frontmatter_value(path: Path, key: str) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing frontmatter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"unterminated frontmatter: {path}")
    prefix = f"{key}:"
    for line in text[4:end].splitlines():
        if line.startswith(prefix):
            value = line.split(":", 1)[1].strip()
            if value:
                return value
    raise ValueError(f"missing {key!r} in frontmatter: {path}")


def _code_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def current_inventory() -> dict[str, Any]:
    installed_skills = sorted(
        path.name for path in SKILLS.iterdir() if (path / "SKILL.md").is_file()
    )
    native_agents = sorted(
        _frontmatter_value(path, "name") for path in AGENTS.glob("*.md")
    )
    kit_skills = sorted(
        path.name
        for path in (KIT_RESOURCES / "skills").iterdir()
        if (path / "SKILL.md").is_file()
    )
    kit_roles = sorted(
        _frontmatter_value(path, "id")
        for path in (KIT_RESOURCES / "roles").glob("*.md")
    )

    kit_skill_root = (KIT_RESOURCES / "skills").resolve()
    managed_skills = []
    for name in installed_skills:
        path = SKILLS / name
        if path.is_symlink() and path.resolve().is_relative_to(kit_skill_root):
            managed_skills.append(name)
    xin_skills = sorted(set(installed_skills) - set(managed_skills))

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["mcpServers"]
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))["profiles"]
    default_servers = profiles["default"]["servers"]
    if len(default_servers) != len(set(default_servers)):
        raise ValueError("default MCP profile contains duplicate servers")
    missing = sorted(set(default_servers) - set(catalog))
    if missing:
        raise ValueError(f"default MCP profile references unknown servers: {missing}")

    return {
        "installed_skills": installed_skills,
        "managed_skills": managed_skills,
        "xin_skills": xin_skills,
        "native_agents": native_agents,
        "kit_skills": kit_skills,
        "kit_roles": kit_roles,
        "catalog_servers": sorted(catalog),
        "default_servers": default_servers,
        "profiles": profiles,
    }


def _skills_block(data: dict[str, Any]) -> str:
    rows = (
        ("Installed project skills", data["installed_skills"]),
        ("Kit-managed installed skills", data["managed_skills"]),
        ("XIN-owned installed skills", data["xin_skills"]),
        ("Native XIN agents", data["native_agents"]),
        ("Vendored kit skill catalog", data["kit_skills"]),
        ("Vendored kit role catalog", data["kit_roles"]),
    )
    lines = [
        BEGIN,
        "## Current resource inventory",
        "",
        "Generated from the live project overlay and vendored kit. Run",
        "`python3 .claude/scripts/sync_doc_inventory.py --write` after changing either inventory.",
        "",
    ]
    for label, values in rows:
        lines.append(f"- **{label} ({len(values)})**: {_code_list(values)}")
    lines.append(END)
    return "\n".join(lines)


def _mcp_block(data: dict[str, Any]) -> str:
    lines = [
        BEGIN,
        "## Current MCP inventory",
        "",
        "Generated from `.claude/mcp-catalog.json` and `.claude/tool-profiles.json`.",
        "This is configuration inventory, not proof that a server connected or a tool passed.",
        "",
        f"- **Default profile ({len(data['default_servers'])} servers)**: "
        f"{_code_list(data['default_servers'])}",
        f"- **Full catalog ({len(data['catalog_servers'])} servers)**: "
        f"{_code_list(data['catalog_servers'])}",
        "",
        "| Profile | Configured servers |",
        "| --- | --- |",
    ]
    for name, profile in data["profiles"].items():
        lines.append(f"| `{name}` | {_code_list(profile['servers'])} |")
    lines.append(END)
    return "\n".join(lines)


def _readme_block(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            BEGIN,
            "## Current local surface",
            "",
            f"The current checkout exposes **{len(data['installed_skills'])} project skills**, "
            f"**{len(data['native_agents'])} native agents**, and "
            f"**{len(data['default_servers'])} MCP servers in the default profile**. "
            f"The vendored kit catalogs **{len(data['kit_skills'])} reusable skills** and "
            f"**{len(data['kit_roles'])} reusable roles**. See [Skills and agents](SKILLS.md) "
            "and the [MCP reference](TOOL_REFERENCE.md) for generated IDs.",
            END,
        ]
    )


def expected_blocks() -> dict[Path, str]:
    data = current_inventory()
    return {
        DOCS / "SKILLS.md": _skills_block(data),
        DOCS / "TOOL_REFERENCE.md": _mcp_block(data),
        DOCS / "README.md": _readme_block(data),
    }


def _replace_block(path: Path, block: str) -> str:
    text = path.read_text(encoding="utf-8")
    matches = list(BLOCK_RE.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one generated inventory block: {path}")
    return BLOCK_RE.sub(block, text, count=1)


def run(write: bool) -> int:
    mismatches: list[Path] = []
    for path, block in expected_blocks().items():
        actual = path.read_text(encoding="utf-8")
        expected = _replace_block(path, block)
        if actual == expected:
            continue
        mismatches.append(path)
        if write:
            path.write_text(expected, encoding="utf-8")
            print(f"[DOC-INVENTORY] Wrote {path.relative_to(ROOT)}")
    if write:
        return 0
    if mismatches:
        for path in mismatches:
            print(
                f"[DOC-INVENTORY] OUT-OF-DATE: {path.relative_to(ROOT)}",
                file=sys.stderr,
            )
        print(
            "Run: python3 .claude/scripts/sync_doc_inventory.py --write",
            file=sys.stderr,
        )
        return 2
    print("[DOC-INVENTORY] Current inventory blocks are synchronized")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="check generated blocks (default)"
    )
    mode.add_argument("--write", action="store_true", help="refresh generated blocks")
    args = parser.parse_args()
    try:
        return run(args.write)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[DOC-INVENTORY] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
