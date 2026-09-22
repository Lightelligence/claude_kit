#!/usr/bin/env python3
"""Measure stable Loop instruction bundles and enforce context budgets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from framework_project import project_root, instruction_text

ROOT = project_root()
LOOP_POLICY = json.loads((ROOT / ".claude/loop_policy.json").read_text(encoding="utf-8"))
MODE_BUDGETS = {
    mode: LOOP_POLICY["modes"][mode]["execution"]["instruction_budget_words"]
    for mode in ("dev", "merge", "signoff")
}
FILE_BUDGETS = {
    "CLAUDE.md": 450,
    ".claude/skills/vibe-soc-loop/SKILL.md": 300,
    ".claude/skills/soc-pipeline/SKILL.md": 260,
    ".claude/agents/soc-reviewer.md": 220,
}
DELIVERY_ROUTER_FILES = (
    "CLAUDE.md",
    ".claude/skills/vibe-soc-loop/SKILL.md",
    ".claude/skills/soc-pipeline/SKILL.md",
    ".claude/rules/01_swarm_flow.md",
    ".claude/rules/02_toolchain.md",
    ".claude/rules/05_pipeline_state.md",
    ".claude/rules/04_coding_style.md",
    ".claude/rules/06_design_knowledge.md",
    ".claude/rules/10_rtl_change_gate.md",
    ".claude/rules/11_verif_recovery_gate.md",
    ".claude/rules/12_syn_pd_gate.md",
    ".claude/rules/13_review_gate.md",
)
BUNDLES = {
    "dev_rtl": {
        "budget":
        MODE_BUDGETS["dev"],
        "files": (
            "CLAUDE.md",
            ".claude/skills/vibe-soc-loop/SKILL.md",
            ".claude/agents/soc-rtl-designer.md",
            ".claude/rules/10_rtl_change_gate.md",
            ".claude/rules/04_coding_style.md",
            ".claude/rules/06_design_knowledge.md",
        ),
    },
    "delivery_merge_router": {
        "budget": MODE_BUDGETS["merge"],
        "files": DELIVERY_ROUTER_FILES,
    },
    "delivery_signoff_router": {
        "budget": MODE_BUDGETS["signoff"],
        "files": DELIVERY_ROUTER_FILES,
    },
}


def word_count(relative: str) -> int:
    text = instruction_text(ROOT / relative, ROOT)
    return len(re.findall(r"\S+", text))


def automatic_rule_budget(root: Path | None = None) -> dict:
    """Measure unconditional rule bytes, not tokenizer or live-session usage.

    Recognize the project's quoted-list paths convention conservatively;
    unknown/malformed scope syntax stays in the unconditional budget.
    """
    root = root or ROOT
    files, scoped = {}, []
    for path in sorted((root / '.claude/rules').rglob('*.md')):
        text = path.read_text(encoding='utf-8')
        parts = text.split('\n---\n', 1) if text.startswith('---\n') else []
        metadata = parts[0][4:] if len(parts) == 2 else ''
        lines = metadata.splitlines()
        quoted_paths = (lines and lines[0] == 'paths:' and len(lines) > 1
                        and all(re.fullmatch(r'  - "[^"\n]+"', line) for line in lines[1:]))
        relative = path.relative_to(root).as_posix()
        if quoted_paths:
            scoped.append(relative)
        else:
            files[relative] = len(text.encode('utf-8'))
    size = sum(files.values())
    return {'utf8_bytes': size, 'budget_bytes': 10000, 'pass': size <= 10000,
            'unconditional_files': files, 'path_scoped_files': scoped,
            'measurement': 'repository rule text only; excludes session, ancestor memory and MCP schemas'}


def report() -> dict:
    files = {
        path: {
            "words": word_count(path),
            "budget": budget,
            "pass": word_count(path) <= budget,
        }
        for path, budget in FILE_BUDGETS.items()
    }
    bundles = {}
    for name, spec in BUNDLES.items():
        words = sum(word_count(path) for path in spec["files"])
        bundles[name] = {
            "words": words,
            "budget": spec["budget"],
            "pass": words <= spec["budget"],
            "files": list(spec["files"]),
        }
    rules = automatic_rule_budget()
    return {
        "pass": rules['pass'] and all(item["pass"] for item in (*files.values(), *bundles.values())),
        "files": files,
        "bundles": bundles,
        "automatic_rules": rules,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when a budget is exceeded")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = report()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for kind in ("files", "bundles"):
            for name, item in result[kind].items():
                status = "PASS" if item["pass"] else "FAIL"
                print(f"{status} {kind[:-1]} {name}: {item['words']}/{item['budget']} words")
        rules = result['automatic_rules']
        print(f"{'PASS' if rules['pass'] else 'FAIL'} automatic rules: {rules['utf8_bytes']}/{rules['budget_bytes']} UTF-8 bytes")
    return 2 if args.check and not result["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
