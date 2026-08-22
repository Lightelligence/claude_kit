from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claude_kit.core import (
    KitError,
    doctor,
    inspect_project,
    load_profile,
    read_artifact,
    resolve_context,
    role_catalog,
    pack_catalog,
    run_project_command,
    validate_profile,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_project"


class CoreTests(unittest.TestCase):
    def test_catalogs_have_expected_entries(self) -> None:
        self.assertIn("reviewer", {item["id"] for item in role_catalog()})
        self.assertIn("protocols.apb", {item["id"] for item in pack_catalog()})

    def test_doctor_passes_fixture(self) -> None:
        result = doctor(FIXTURE, strict=True)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["issues"], [])

    def test_context_and_manifest_have_sources(self) -> None:
        profile_path, profile = load_profile(FIXTURE)
        context, manifest = resolve_context(
            FIXTURE,
            profile_path,
            profile,
            ["reviewer"],
            ["common", "protocols.apb"],
            "review APB reset behavior",
        )
        self.assertIn("review APB reset behavior", context)
        self.assertIn("APB Guidance", context)
        self.assertEqual(manifest["project"], "minimal_fixture")
        self.assertTrue(manifest["sources"])
        self.assertTrue(all(item["sha256"] for item in manifest["sources"]))

    def test_inspect_uses_profile_roots(self) -> None:
        _, profile = load_profile(FIXTURE)
        result = inspect_project(FIXTURE, profile)
        self.assertEqual(result["groups"]["rtl"]["files"], 1)
        self.assertEqual(result["groups"]["dv"]["files"], 1)

    def test_read_artifact_rejects_escape(self) -> None:
        with self.assertRaises(KitError):
            read_artifact(FIXTURE, "../README.md")

    def test_command_confirmation_and_execution(self) -> None:
        _, profile = load_profile(FIXTURE)
        with self.assertRaises(KitError):
            run_project_command(FIXTURE, profile, "confirmed")
        result = run_project_command(FIXTURE, profile, "confirmed", confirm=True)
        self.assertEqual(result["status"], "passed")
        self.assertIn("fixture confirmed", result["stdout"])

    def test_invalid_permission_overlap_is_reported(self) -> None:
        profile = {
            "schema_version": 1,
            "project": {"id": "bad"},
            "permissions": {"writable": ["rtl/**"], "read_only": ["rtl/**"]},
        }
        issues = validate_profile(FIXTURE, profile)
        self.assertTrue(any("permissions overlap" in item["message"] for item in issues))

    def test_init_is_non_destructive_without_force(self) -> None:
        from claude_kit.core import init_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / ".claude" / "CLAUDE.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("keep me", encoding="utf-8")
            created = init_project(root)
            self.assertIn(".ai/project.toml", created)
            self.assertNotIn(".claude/CLAUDE.md", created)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep me")


if __name__ == "__main__":
    unittest.main()
