#!/usr/bin/env python3
"""Check the concise Claude Code Loop contract across canonical files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from framework_project import project_root, instruction_text

ROOT = project_root()
REQUIRED = {
    "CLAUDE.md": ("Claude Code entry point", "registered MCP servers", "hw/**"),
    "SETUP.md": ("Claude Code", "registered MCP servers", "DV validation menu"),
    ".claude/CLAUDE.md": ("Normal Claude Code workflow", "EDA execution invariant", "MCP-only"),
    ".claude/rules/00_loop_modes.md": ("dev", "merge", "signoff"),
    ".claude/rules/01_swarm_flow.md": ("doc -> rtl", "one stage owner"),
    ".claude/rules/02_toolchain.md": ("CDC", "`soc_sim` compiles", "Do not run both"),
    ".claude/rules/05_pipeline_state.md": ("--compact", "immutable artifact paths"),
    ".claude/rules/13_review_gate.md": (
        "Project Rule",
        "Need Human Confirmation",
        "Never state that the design is signed off",
    ),
    ".claude/skills/vibe-soc-loop/SKILL.md": (
        "fewest useful tool loops",
        "compact state",
        "one matching owner",
        "preflight",
        "same-failure retry limit",
    ),
    ".claude/skills/soc-pipeline/SKILL.md": ("`merge`", "`signoff`", "registered checks"),
    ".claude/skills/soc-openroad/SKILL.md": ("PD handoff summary", "work_local"),
    ".claude/skills/soc-openroad/mcp_server.py": (
        'DEFAULT_LOCAL_ORFS_DIR = ""',
        "SILICON_CREW_ORFS_DIR",
    ),
    ".claude/agents/soc-pd-engineer.md": ("configured ORFS directory", ),
    ".claude/agents/soc-reviewer.md": ("13_review_gate.md", "Do not write"),
}
FORBIDDEN = {
    ".claude/rules/05_pipeline_state.md": ("CLAUDE_PLUGIN_ROOT", ),
}


def violations() -> list[str]:
    errors: list[str] = []
    for relative, tokens in REQUIRED.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"{relative}: missing")
            continue
        text = instruction_text(path, ROOT)
        errors.extend(f"{relative}: missing required contract {token!r}" for token in tokens if token not in text)
    for relative, tokens in FORBIDDEN.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        errors.extend(f"{relative}: contains forbidden local/legacy contract {token!r}" for token in tokens
                      if token in text)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument(
        "--write",
        action="store_true",
        help="compatibility alias; contracts are canonical and are never rewritten",
    )
    args = parser.parse_args()
    errors = violations()
    if errors:
        for error in errors:
            print(f"[LOOP-CONTRACT] ERROR: {error}", file=sys.stderr)
        return 2
    if args.write:
        print("[LOOP-CONTRACT] Canonical contracts already satisfy invariants")
    else:
        print("[LOOP-CONTRACT] Cross-file contract invariants pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
