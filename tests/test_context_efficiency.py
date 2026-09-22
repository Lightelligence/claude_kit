"""Behavioral checks for small, compatible RTL/DV context selection."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claude_kit.core import (
    KitError, integration_skill, load_profile, resolve_context, resolve_plan,
    resource_root, skill_catalog, sync_project_skills, workflow_catalog,
)
from claude_kit.deployment import attach_project

FIXTURE = Path(__file__).resolve().parent / "fixtures/minimal_project"


class ContextEfficiencyTests(unittest.TestCase):
    def test_catalog_and_materialization_expose_one_context_skill(self):
        entries = {entry["id"]: entry for entry in skill_catalog()}
        self.assertIn("rtl-dv-kit", entries)
        self.assertNotIn("rtl-dv-context", entries)
        canonical = resource_root() / entries["rtl-dv-kit"]["path"]
        self.assertEqual(integration_skill(), canonical.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sync_project_skills(root)
            self.assertTrue((root / ".claude/skills/rtl-dv-kit/SKILL.md").is_file())
            self.assertFalse((root / ".claude/skills/rtl-dv-context").exists())

    def test_legacy_and_duplicate_requests_load_guidance_once(self):
        path, profile = load_profile(FIXTURE)
        canonical = resolve_context(FIXTURE, path, profile, ["reviewer"], ["common"],
                                    "review reset", ["rtl-dv-kit"])
        repeated = resolve_context(FIXTURE, path, profile, ["reviewer", "reviewer"],
                                   ["common", "common"], "review reset",
                                   ["rtl-dv-context", "rtl-dv-kit", "rtl-dv-context"])
        self.assertEqual(repeated, canonical)
        self.assertEqual(len({s["path"] for s in repeated[1]["sources"]}),
                         len(repeated[1]["sources"]))

    def test_explicit_empty_selections_do_not_load_profile_defaults(self):
        path, profile = load_profile(FIXTURE)
        with patch("claude_kit.core.skill_catalog", side_effect=AssertionError("unrelated skill read")):
            _, manifest = resolve_context(FIXTURE, path, profile, [], [], "known edit", [])
            resolve_context(FIXTURE, path, profile, [], [], "known edit", None)
        self.assertEqual(manifest["sources"], [])
        self.assertEqual(manifest["roles"], [])
        self.assertEqual(manifest["packs"], [])

    def test_selected_skills_read_catalog_only_once(self):
        path, profile = load_profile(FIXTURE)
        with patch("claude_kit.core.skill_catalog", wraps=skill_catalog) as catalog:
            resolve_context(FIXTURE, path, profile, [], [], "review",
                            ["rtl-dv-kit", "rtl-dv-context", "rtl-dv-review"])
            catalog.assert_called_once_with()

    def test_legacy_plus_canonical_owner_is_rejected_before_writes(self):
        for selection in ('skills = ["rtl-dv-context", "rtl-dv-kit"]\n',
                          'skills = ["rtl-dv-context"]\nframework = "soc"\n'):
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / ".claude").mkdir()
                manifest = root / ".claude/kit-attachment.toml"
                manifest.write_text('schema_version = 1\nmanage_profile = false\n'
                                    'manage_mcp = false\nroles = []\n' + selection)
                with patch("claude_kit.deployment.os.replace") as replace:
                    with self.assertRaisesRegex(KitError, "Duplicate skill selection"):
                        attach_project(root, manifest=manifest)
                    replace.assert_not_called()
                self.assertFalse((root / ".claude/skills").exists())

    def test_plan_selects_primary_guidance_not_auxiliary_workflows(self):
        path, profile = load_profile(FIXTURE)
        for workflow in workflow_catalog():
            with self.subTest(workflow=workflow["id"]):
                plan = resolve_plan(FIXTURE, path, profile, workflow["id"], None,
                                    None, workflow["summary"])
                for identifier in plan["skills"]:
                    self.assertIn(identifier, {e["id"] for e in skill_catalog()})
                if workflow["id"] in {"dv-change", "debug", "review"}:
                    self.assertNotIn("rtl-dv-regression", plan["skills"])
                    self.assertNotIn("rtl-dv-evidence", plan["skills"])
                    self.assertNotIn("rtl-dv-kit", plan["skills"])
                for check in plan["check_plan"]:
                    if check["category"] in {"simulation", "regression", "coverage", "synthesis", "cdc"}:
                        self.assertFalse(check["recommended"])
                        self.assertTrue(check["requires_confirmation"])

    def test_explicit_legacy_attachment_remains_usable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".claude").mkdir()
            manifest = root / ".claude/kit-attachment.toml"
            manifest.write_text('schema_version = 1\nmanage_profile = false\n'
                                'manage_mcp = false\nroles = []\n'
                                'skills = ["rtl-dv-context"]\n', encoding="utf-8")
            attach_project(root, manifest=manifest)
            legacy = root / ".claude/skills/rtl-dv-context/SKILL.md"
            self.assertEqual(legacy.read_text(encoding="utf-8"), integration_skill())
            self.assertEqual(attach_project(root, manifest=manifest)["changed"], [])

    def test_old_vendored_catalog_without_new_skill_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory)
            legacy = resources / "skills/rtl-dv-context/SKILL.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text('---\nname: rtl-dv-context\ndescription: Legacy kit\n---\n')
            self.assertEqual([entry["id"] for entry in skill_catalog(resources)],
                             ["rtl-dv-context"])


if __name__ == "__main__":
    unittest.main()
