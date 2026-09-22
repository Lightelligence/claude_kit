#!/usr/bin/env python3
"""Normalize canonical Markdown role contracts for Claude Code."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from framework_project import project_root, require_project_owned

ROOT = project_root()
CANONICAL_DIR = ROOT / ".claude" / "agents"
HELPERS = (
    "update_state.py",
    "query_state.py",
    "check_doc_completeness.py",
    "check_rtl_quality.py",
    "check_sim_pass.py",
    "check_timing.py",
    "check_loop_state.py",
)
HELPER_RE = re.compile(r"(?<![A-Za-z0-9_./-])scripts/(" + "|".join(re.escape(name) for name in HELPERS) + r")")

# Root sessions keep only commonly useful generators enabled. These role-local
# overrides activate heavyweight servers only for the agent that owns them.


def parse_contract(path: Path) -> tuple[str, str, str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing frontmatter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"unterminated frontmatter: {path}")
    frontmatter = text[4:end]
    body = text[end + 5:].strip() + "\n"
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if line.startswith(("name:", "description:")):
            key, value = line.split(":", 1)
            fields[key] = value.strip()
    name = fields.get("name", "")
    description = fields.get("description", "")
    if not name or not description or path.stem != name:
        raise ValueError(f"invalid role metadata: {path}")
    return name, description, frontmatter, body


def normalize_body(body: str) -> str:
    normalized = HELPER_RE.sub(r"<project_root>/.claude/scripts/\1", body)
    return normalized.rstrip() + "\n"


def render_markdown(frontmatter: str, body: str) -> str:
    return f"---\n{frontmatter.rstrip()}\n---\n\n{body}"


def expected() -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    paths = sorted(CANONICAL_DIR.glob("soc-*.md"))
    if not paths:
        raise ValueError("no canonical role contracts found")
    for path in paths:
        _, _, frontmatter, body = parse_contract(path)
        outputs[path] = render_markdown(frontmatter, normalize_body(body))
    return outputs


def run(write: bool) -> int:
    mismatches: list[Path] = []
    for path, content in expected().items():
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual == content:
            continue
        mismatches.append(path)
        if write:
            require_project_owned(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"[AGENT-PROFILE] Wrote {path.relative_to(ROOT)}")
    if write:
        return 0
    if mismatches:
        for path in mismatches:
            print(f"[AGENT-PROFILE] OUT-OF-DATE: {path.relative_to(ROOT)}", file=sys.stderr)
        print("Run: python3 .claude/scripts/sync_agent_profiles.py --write", file=sys.stderr)
        return 2
    print("[CLAUDE-PROFILE] Markdown role contracts are synchronized")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify generated adapters (default)")
    mode.add_argument("--write", action="store_true", help="normalize contracts and regenerate adapters")
    args = parser.parse_args()
    try:
        return run(args.write)
    except (OSError, ValueError) as exc:
        print(f"[AGENT-PROFILE] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
