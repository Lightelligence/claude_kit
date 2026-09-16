"""Deployment/routing contracts for the consolidated RTL/DV workflow skills."""
from __future__ import annotations

import os
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claude_kit.core import (
    KitError, init_project, integration_skill, resource_root, resolve_plan, resolve_context,
    load_profile, skill_catalog, sync_project_skills, workflow_catalog,
)
from claude_kit.deployment import attach_project

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "dv-engineering", "rtl-dv-kit",
    "rtl-dv-evidence", "rtl-dv-regression", "rtl-dv-debugging",
)


def linked_files(base: Path, start: Path):
    """Follow local Markdown references, including cross-skill compatibility links."""
    pending = [start]
    seen = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        assert path.is_file(), str(path)
        yield path
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            linked = Path(os.path.normpath(path.parent / target.split("#")[0]))
            assert linked.is_relative_to(base), str(linked)
            pending.append(linked)


class WorkflowSkillTests(unittest.TestCase):
    def test_canonical_integration_is_catalogued_without_visible_alias(self):
        catalog = {entry["id"]: entry for entry in skill_catalog()}
        self.assertTrue(set(NAMES).issubset(catalog))
        self.assertNotIn("rtl-dv-context", catalog)
        canonical = resource_root() / catalog["rtl-dv-kit"]["path"]
        self.assertEqual(integration_skill(), canonical.read_text(encoding="utf-8"))
        self.assertFalse((resource_root() / "templates/SKILL.md").exists())

    def test_all_selected_references_survive_full_sync(self):
        source_base = resource_root() / "skills"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sync_project_skills(root)
            deployed_base = root / ".claude/skills"
            self.assertFalse((deployed_base / "rtl-dv-context").exists())
            for name in NAMES:
                with self.subTest(skill=name):
                    source_files = list(linked_files(source_base, source_base / name / "SKILL.md"))
                    deployed_files = list(linked_files(deployed_base, deployed_base / name / "SKILL.md"))
                    self.assertEqual(len(source_files), len(deployed_files))
                    for original in source_files:
                        deployed = deployed_base / original.relative_to(source_base)
                        self.assertEqual(deployed.read_text(encoding="utf-8"),
                                         original.read_text(encoding="utf-8").rstrip() + "\n")
            self.assertEqual(sync_project_skills(root), [])

    def test_minimal_init_is_self_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, minimal=True)
            base = root / ".claude/skills"
            self.assertEqual({p.name for p in base.iterdir()}, {"rtl-dv-kit"})
            self.assertEqual(list(linked_files(base, base / "rtl-dv-kit/SKILL.md")),
                             [base / "rtl-dv-kit/SKILL.md"])
            self.assertEqual((base / "rtl-dv-kit/SKILL.md").read_text(encoding="utf-8"),
                             integration_skill())

    def test_shared_attachment_resolves_cross_skill_links_without_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attach_project(root)
            base = root / ".claude/skills"
            for name in NAMES:
                with self.subTest(skill=name):
                    self.assertTrue((base / name).is_symlink())
                    self.assertTrue(list(linked_files(base, base / name / "SKILL.md")))
            self.assertFalse((base / "rtl-dv-context").exists())
            self.assertEqual(attach_project(root)["changed"], [])

    def test_sync_preserves_customized_legacy_entry_without_force(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sync_project_skills(root)
            alias = root / ".claude/skills/rtl-dv-context/SKILL.md"
            alias.parent.mkdir()
            custom = "# Project-owned context override\n"
            alias.write_text(custom, encoding="utf-8")
            sync_project_skills(root)
            self.assertEqual(alias.read_text(encoding="utf-8"), custom)

    def test_attachment_retires_only_unchanged_managed_context_link(self):
        for customized in (False, True):
            with self.subTest(customized=customized), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                attach_project(root)
                legacy = root / ".claude/skills/rtl-dv-context"
                target = root / "legacy-context"
                target.mkdir()
                (target / "SKILL.md").write_text("original", encoding="utf-8")
                legacy.symlink_to(target, target_is_directory=True)
                state_path = root / ".claude/kit-state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["managed"][".claude/skills/rtl-dv-context"] = "link:" + os.readlink(legacy)
                state_path.write_text(json.dumps(state), encoding="utf-8")
                if customized:
                    legacy.unlink()
                    legacy.mkdir()
                    (legacy / "SKILL.md").write_text("custom", encoding="utf-8")
                attach_project(root, dry_run=True)
                self.assertTrue(legacy.exists())
                if not customized:
                    original_state = state_path.read_bytes()
                    replace = os.replace

                    def fail_state(source, destination):
                        if Path(destination) == state_path:
                            raise OSError("injected retirement failure")
                        return replace(source, destination)

                    with patch("claude_kit.deployment.os.replace", side_effect=fail_state):
                        with self.assertRaisesRegex(KitError, "rolled back"):
                            attach_project(root)
                    self.assertTrue(legacy.is_symlink())
                    self.assertEqual(state_path.read_bytes(), original_state)
                result = attach_project(root)
                self.assertEqual(legacy.exists(), customized)
                self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "original")
                self.assertEqual(".claude/skills/rtl-dv-context" in result["retired_managed_paths"], customized)
                self.assertEqual(attach_project(root)["changed"], [])

    def test_plans_select_canonical_context_not_both_entries(self):
        for workflow in workflow_catalog():
            self.assertIn("rtl-dv-kit", workflow["skills"])
            self.assertNotIn("rtl-dv-context", workflow["skills"])
        root = ROOT / "tests/fixtures/minimal_project"
        profile_path, profile = load_profile(root)
        plan = resolve_plan(root, profile_path, profile, "auto", None, None,
                            "debug scoreboard failure")
        self.assertIn("rtl-dv-kit", plan["skills"])
        self.assertNotIn("rtl-dv-context", plan["skills"])
        context, manifest = resolve_context(root, profile_path, profile, [], [], "context",
                                            ["rtl-dv-context", "rtl-dv-kit"])
        self.assertEqual(context.count(integration_skill().strip()), 1)
        self.assertEqual(len(manifest["sources"]), 1)


if __name__ == "__main__":
    unittest.main()
