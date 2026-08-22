from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claude_kit.core import (
    KitError,
    check_adapter,
    doctor,
    inspect_project,
    load_profile,
    mcp_config,
    read_artifact,
    resolve_context,
    role_catalog,
    pack_catalog,
    review_evidence_file,
    run_project_command,
    skill_catalog,
    sync_project_skills,
    validate_profile,
    validate_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_project"


class CoreTests(unittest.TestCase):
    def test_catalogs_have_expected_entries(self) -> None:
        self.assertIn("reviewer", {item["id"] for item in role_catalog()})
        self.assertIn("waveform-debugger", {item["id"] for item in role_catalog()})
        self.assertIn("protocols.apb", {item["id"] for item in pack_catalog()})
        self.assertIn("protocols.chi", {item["id"] for item in pack_catalog()})
        self.assertIn("protocols.axi4lite", {item["id"] for item in pack_catalog()})
        self.assertIn("rtl-design", {item["id"] for item in skill_catalog()})
        self.assertIn("rtl-dv-evidence", {item["id"] for item in skill_catalog()})

    def test_project_schema_describes_runtime_profile_contract(self) -> None:
        schema_path = ROOT / "src" / "claude_kit" / "resources" / "schemas" / "project.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertIn("commands", schema["properties"]["build"]["properties"])
        self.assertIn("required_functions", schema["properties"]["adapter"]["oneOf"][1]["properties"])
        self.assertEqual(schema["properties"]["packs"]["type"], "array")

        evidence_schema = json.loads(
            (ROOT / "src" / "claude_kit" / "resources" / "schemas" / "evidence.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(evidence_schema["properties"]["checks"]["items"]["properties"]["status"]["enum"][0], "passed")

    def test_doctor_passes_fixture(self) -> None:
        result = doctor(FIXTURE, strict=True)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["issues"], [])

    def test_context_and_manifest_have_sources(self) -> None:
        profile_path, profile = load_profile(FIXTURE)
        self.assertEqual(profile["packs"], ["common", "protocols.apb"])
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
        _, default_manifest = resolve_context(FIXTURE, profile_path, profile, None, None, "use profile defaults")
        self.assertEqual(default_manifest["packs"], ["common", "protocols.apb"])

    def test_inspect_uses_profile_roots(self) -> None:
        _, profile = load_profile(FIXTURE)
        result = inspect_project(FIXTURE, profile)
        self.assertEqual(result["groups"]["rtl"]["files"], 1)
        self.assertEqual(result["groups"]["dv"]["files"], 1)

    def test_read_artifact_rejects_escape(self) -> None:
        with self.assertRaises(KitError):
            read_artifact(FIXTURE, "../README.md")
        result = read_artifact(FIXTURE, "out/logs/README.md", 4)
        self.assertTrue(result["truncated"])
        with self.assertRaises(KitError):
            read_artifact(FIXTURE, "out/logs/README.md", 1_000_001)

    def test_explicit_profile_and_inspect_roots_cannot_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(KitError):
                load_profile(root, "../outside.toml")
            with self.assertRaises(KitError):
                inspect_project(root, {"roots": {"rtl": ["../outside"]}})

    def test_evidence_contract_passes_and_rejects_read_only_change(self) -> None:
        _, profile = load_profile(FIXTURE)
        result = review_evidence_file(FIXTURE, profile, "out/evidence.json", strict=True)
        self.assertEqual(result["status"], "passed", result)
        bad = {
            "schema_version": 1,
            "project": "minimal_fixture",
            "task": "bad change",
            "changes": ["generated/README.md"],
            "checks": [{"name": "inspect", "status": "passed", "command": ["inspect"]}],
        }
        issues = validate_evidence(FIXTURE, profile, bad, strict=True)
        self.assertTrue(any("outside the writable scope" in item["message"] for item in issues))

    def test_command_confirmation_and_execution(self) -> None:
        _, profile = load_profile(FIXTURE)
        with self.assertRaises(KitError):
            run_project_command(FIXTURE, profile, "confirmed")
        result = run_project_command(FIXTURE, profile, "confirmed", confirm=True)
        self.assertEqual(result["status"], "passed")
        self.assertIn("fixture confirmed", result["stdout"])

    def test_command_timeout_returns_structured_failure(self) -> None:
        profile = {
            "project": {"id": "timeout_fixture"},
            "build": {
                "commands": {
                    "hang": {
                        "argv": ["python", "-c", "import time; time.sleep(2)"],
                        "cwd": ".",
                    }
                }
            },
        }
        result = run_project_command(FIXTURE, profile, "hang", timeout=1)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["returncode"])

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
            _, generated_profile = load_profile(root)
            self.assertEqual(generated_profile["packs"], ["common"])

    def test_init_minimal_keeps_project_skill_footprint_small(self) -> None:
        from claude_kit.core import init_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created = init_project(root, minimal=True)
            self.assertIn(".claude/skills/rtl-dv-kit/SKILL.md", created)
            self.assertNotIn(".claude/skills/rtl-design/SKILL.md", created)

    def test_mcp_config_is_wrapped_and_points_to_pinned_kit(self) -> None:
        config = json.loads(mcp_config("third_party\\claude_kit"))
        server = config["mcpServers"]["claude-kit"]
        self.assertEqual(server["command"], "python")
        self.assertEqual(server["args"][0], "third_party/claude_kit/bin/claude-kit")
        self.assertIn("--profile", server["args"])

    def test_sync_materializes_all_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            created = sync_project_skills(Path(directory))
            self.assertGreaterEqual(len(created), 7)
            self.assertTrue((Path(directory) / ".claude/skills/rtl-design/SKILL.md").is_file())
            self.assertTrue((Path(directory) / ".claude/skills/rtl-dv-evidence/SKILL.md").is_file())

    def test_adapter_check_imports_only_explicit_project_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root / ".ai" / "adapter.py"
            adapter.parent.mkdir(parents=True)
            adapter.write_text("def resolve_target(name):\n    return name\n", encoding="utf-8")
            profile = {"project": {"id": "adapter_fixture"}, "adapter": {"path": ".ai/adapter.py", "required_functions": ["resolve_target"]}}
            result = check_adapter(root, profile)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["functions"], ["resolve_target"])
            self.assertIn("resolve_target", result["signatures"])

            adapter.write_text(
                "def resolve_target(name):\n    return name\n\ndef project_check(name):\n    return name\n",
                encoding="utf-8",
            )
            profile["adapter"]["required_functions"] = ["resolve_target", "project_check"]
            custom = check_adapter(root, profile)
            self.assertEqual(custom["status"], "passed", custom)
            self.assertIn("project_check", custom["functions"])

            adapter.write_text("def resolve_target():\n    return 'bad'\n", encoding="utf-8")
            profile["adapter"]["required_functions"] = ["resolve_target"]
            invalid = check_adapter(root, profile)
            self.assertEqual(invalid["status"], "failed", invalid)
            self.assertTrue(any("at least one argument" in item["message"] for item in invalid["issues"]))


if __name__ == "__main__":
    unittest.main()
