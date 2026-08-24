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
    command_menu,
    doctor,
    inspect_project,
    load_profile,
    mcp_config,
    read_artifact,
    resolve_context,
    role_catalog,
    pack_catalog,
    review_evidence_file,
    run_project_commands,
    run_project_command,
    skill_catalog,
    sync_project_skills,
    validate_profile,
    validate_evidence,
    resolve_plan,
    workflow_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_project"


class CoreTests(unittest.TestCase):
    def test_catalogs_have_expected_entries(self) -> None:
        self.assertIn("reviewer", {item["id"] for item in role_catalog()})
        self.assertIn("waveform-debugger", {item["id"] for item in role_catalog()})
        self.assertIn("commander", {item["id"] for item in role_catalog()})
        self.assertIn("protocols.apb", {item["id"] for item in pack_catalog()})
        self.assertIn("protocols.chi", {item["id"] for item in pack_catalog()})
        self.assertIn("protocols.axi4lite", {item["id"] for item in pack_catalog()})
        self.assertIn("rtl-design", {item["id"] for item in skill_catalog()})
        self.assertIn("rtl-dv-evidence", {item["id"] for item in skill_catalog()})

    def test_workflow_catalog_resolves_task_plan(self) -> None:
        self.assertIn("debug", {item["id"] for item in workflow_catalog()})
        profile_path, profile = load_profile(FIXTURE)
        plan = resolve_plan(
            FIXTURE,
            profile_path,
            profile,
            "auto",
            None,
            ["protocols.apb"],
            "debug APB timeout in simulation",
        )
        self.assertEqual(plan["workflow"]["id"], "debug")
        self.assertIn("debugger", plan["roles"])
        self.assertIn("protocols.apb", plan["recommended_packs"])
        self.assertIn("source_revision", plan["missing_facts"])
        self.assertIn("rtl-dv-debugging", plan["skills"])
        self.assertTrue(plan["skill_sources"])
        self.assertEqual(plan["check_plan"][0]["name"], "inspect")
        self.assertEqual(plan["kind"], "rtl-dv-workflow-plan")
        chinese_plan = resolve_plan(
            FIXTURE,
            profile_path,
            profile,
            "auto",
            None,
            None,
            "调试 APB 超时",
        )
        self.assertEqual(chinese_plan["workflow"]["id"], "debug")
        for workflow in workflow_catalog():
            resolved = resolve_plan(
                FIXTURE,
                profile_path,
                profile,
                workflow["id"],
                None,
                None,
                workflow["summary"],
            )
            self.assertEqual(resolved["workflow"]["id"], workflow["id"])

    def test_check_menu_classifies_project_specific_wrappers(self) -> None:
        profile = {
            "project": {"id": "menu_fixture"},
            "build": {
                "commands": {
                    "soc_lint": {"argv": ["python", "-c", "print('lint')"], "kind": "verification"},
                    "soc_comp": {"argv": ["python", "-c", "print('compile')"], "kind": "build"},
                    "soc_sim": {"argv": ["python", "-c", "print('sim')"], "kind": "simulation"},
                    "soc_regress": {"argv": ["python", "-c", "print('regress')"], "kind": "regression"},
                    "soc_coverage": {"argv": ["python", "-c", "print('coverage')"], "kind": "coverage"},
                    "soc_syn": {"argv": ["python", "-c", "print('syn')"], "kind": "synthesis"},
                    "soc_cdc": {"argv": ["python", "-c", "print('cdc')"], "kind": "cdc"},
                }
            },
        }
        menu = {item["name"]: item for item in command_menu(profile)}
        self.assertEqual(menu["soc_lint"]["category"], "lint")
        self.assertEqual(menu["soc_comp"]["category"], "compile")
        for name in ("soc_sim", "soc_regress", "soc_coverage", "soc_syn", "soc_cdc"):
            self.assertEqual(menu[name]["selection"], "explicit")
            self.assertFalse(menu[name]["recommended"])

    def test_mcp_backed_check_is_profiled_but_not_shell_executed(self) -> None:
        profile = {
            "project": {"id": "mcp_fixture"},
            "build": {
                "commands": {
                    "project_lint": {
                        "mcp_server": "project-build",
                        "mcp_tool": "project_lint",
                        "category": "lint",
                        "kind": "verification",
                    }
                }
            },
        }
        menu = command_menu(profile)
        self.assertEqual(menu[0]["execution"], "mcp")
        self.assertEqual(menu[0]["mcp_tool"], "project_lint")
        with self.assertRaisesRegex(KitError, "call the project MCP tool"):
            run_project_command(FIXTURE, profile, "project_lint", confirm=True)

    def test_selected_checks_run_sequentially_with_per_check_reports(self) -> None:
        _, profile = load_profile(FIXTURE)
        result = run_project_commands(FIXTURE, profile, ["inspect", "confirmed"], confirm=True)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["summary"]["passed"], 2)
        self.assertEqual([item["command"] for item in result["results"]], ["inspect", "confirmed"])

    def test_batch_blocks_unconfirmed_expensive_check_and_continues(self) -> None:
        profile = {
            "project": {"id": "batch_gate"},
            "build": {
                "commands": {
                    "simulate": {
                        "argv": ["python", "-c", "print('simulation')"],
                        "cwd": ".",
                        "kind": "simulation",
                    },
                    "inspect": {
                        "argv": ["python", "-c", "print('inspect')"],
                        "cwd": ".",
                        "kind": "read_only",
                    },
                }
            },
        }
        result = run_project_commands(FIXTURE, profile, ["simulate", "inspect"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["summary"]["blocked"], 1)
        self.assertEqual(result["summary"]["passed"], 1)
        self.assertEqual(result["results"][0]["status"], "blocked")
        self.assertEqual(result["results"][1]["status"], "passed")

    def test_project_schema_describes_runtime_profile_contract(self) -> None:
        schema_path = ROOT / "src" / "claude_kit" / "resources" / "schemas" / "project.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertIn("commands", schema["properties"]["build"]["properties"])
        command_schema = schema["properties"]["build"]["properties"]["commands"]["additionalProperties"]["properties"]
        self.assertIn("category", command_schema)
        self.assertIn("artifacts", command_schema)
        self.assertIn("mcp_server", command_schema)
        self.assertIn("mcp_tool", command_schema)
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
            ["rtl-dv-context", "rtl-dv-review"],
        )
        self.assertIn("review APB reset behavior", context)
        self.assertIn("APB Guidance", context)
        self.assertIn("RTL/DV Context", context)
        self.assertIn("RTL/DV Review", context)
        self.assertEqual(manifest["project"], "minimal_fixture")
        self.assertEqual(manifest["skills"], ["rtl-dv-context", "rtl-dv-review"])
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

    def test_explicit_empty_writable_scope_rejects_changes(self) -> None:
        profile = {"project": {"id": "readonly"}, "permissions": {"writable": []}}
        evidence = {
            "schema_version": 1,
            "project": "readonly",
            "task": "read only",
            "changes": ["rtl/README.md"],
            "checks": [{"name": "inspect", "status": "passed", "command": ["inspect"]}],
        }
        issues = validate_evidence(FIXTURE, profile, evidence, strict=True)
        self.assertTrue(any("not covered by permissions.writable" in item["message"] for item in issues))

    def test_evidence_accepts_writable_symlink_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".agents" / "skills"
            target.mkdir(parents=True)
            (root / ".claude").mkdir()
            try:
                (root / ".claude" / "skills").symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")

            profile = {
                "project": {"id": "symlink_fixture"},
                "permissions": {"writable": [".claude/**"]},
            }
            evidence = {
                "schema_version": 1,
                "project": "symlink_fixture",
                "task": "write through the Claude skills alias",
                "changes": [".claude/skills/rtl-dv-kit/SKILL.md"],
                "checks": [{"name": "inspect", "status": "passed", "command": ["inspect"]}],
            }
            issues = validate_evidence(root, profile, evidence, strict=True)
            self.assertFalse(issues, issues)

    def test_command_confirmation_and_execution(self) -> None:
        _, profile = load_profile(FIXTURE)
        with self.assertRaises(KitError):
            run_project_command(FIXTURE, profile, "confirmed")
        result = run_project_command(FIXTURE, profile, "confirmed", confirm=True)
        self.assertEqual(result["status"], "passed")
        self.assertIn("fixture confirmed", result["stdout"])

    def test_simulation_kind_requires_confirmation_by_default(self) -> None:
        profile = {
            "project": {"id": "simulation_gate"},
            "build": {
                "commands": {
                    "simulate": {
                        "argv": ["python", "-c", "print('simulation')"],
                        "cwd": ".",
                        "kind": "simulation",
                    }
                }
            },
        }
        with self.assertRaisesRegex(KitError, "expensive simulation workload"):
            run_project_command(FIXTURE, profile, "simulate")
        result = run_project_command(FIXTURE, profile, "simulate", confirm=True)
        self.assertEqual(result["status"], "passed")

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

    def test_init_no_skills_keeps_project_skill_layer_untouched(self) -> None:
        from claude_kit.core import init_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created = init_project(root, no_skills=True)
            self.assertIn(".ai/project.toml", created)
            self.assertIn(".claude/CLAUDE.md", created)
            self.assertFalse(any(path.startswith(".claude/skills/") for path in created))
            self.assertFalse((root / ".claude" / "skills").exists())

    def test_init_merges_mcp_without_removing_project_servers(self) -> None:
        from claude_kit.core import init_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mcp_path = root / ".mcp.json"
            mcp_path.write_text(
                json.dumps({"mcpServers": {"project-server": {"command": "project-tool"}}}),
                encoding="utf-8",
            )
            created = init_project(root, with_mcp=True, no_skills=True)
            config = json.loads(mcp_path.read_text(encoding="utf-8"))
            self.assertIn("project-server", config["mcpServers"])
            self.assertIn("claude-kit", config["mcpServers"])
            self.assertIn(".mcp.json", created)

            unchanged = init_project(root, with_mcp=True, no_skills=True)
            self.assertNotIn(".mcp.json", unchanged)

    def test_init_rejects_conflicting_mcp_entry_without_force(self) -> None:
        from claude_kit.core import init_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"claude-kit": {"command": "old-kit"}}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(KitError, "different claude-kit server"):
                init_project(root, with_mcp=True, no_skills=True)
            init_project(root, with_mcp=True, force=True, no_skills=True)
            config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertEqual(config["mcpServers"]["claude-kit"]["command"], "python3")

    def test_init_does_not_write_through_external_symlink(self) -> None:
        from claude_kit.core import init_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory).parent / f"claude-kit-outside-{Path(directory).name}.md"
            try:
                outside.write_text("keep me", encoding="utf-8")
                link = root / ".claude" / "CLAUDE.md"
                link.parent.mkdir(parents=True)
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            try:
                with self.assertRaisesRegex(KitError, "symlink|project root"):
                    init_project(root, force=True, no_skills=True)
                self.assertEqual(outside.read_text(encoding="utf-8"), "keep me")
            finally:
                outside.unlink(missing_ok=True)

    def test_init_with_adapter_enables_profile_contract(self) -> None:
        from claude_kit.core import init_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, with_adapter=True)
            _, profile = load_profile(root)
            self.assertEqual(profile["adapter"]["path"], ".ai/adapter.py")
            result = check_adapter(root, profile)
            self.assertEqual(result["status"], "passed", result)

    def test_mcp_config_is_wrapped_and_points_to_pinned_kit(self) -> None:
        config = json.loads(mcp_config("third_party\\claude_kit"))
        server = config["mcpServers"]["claude-kit"]
        self.assertEqual(server["command"], "python3")
        self.assertEqual(server["args"][0], "third_party/claude_kit/bin/claude-kit")
        self.assertIn("--profile", server["args"])

    def test_sync_materializes_all_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            created = sync_project_skills(Path(directory))
            self.assertGreaterEqual(len(created), 7)
            self.assertTrue((Path(directory) / ".claude/skills/rtl-design/SKILL.md").is_file())
            self.assertTrue((Path(directory) / ".claude/skills/rtl-dv-evidence/SKILL.md").is_file())

    def test_sync_rejects_skills_symlink_that_escapes_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / f"claude-kit-skills-outside-{root.name}"
            try:
                outside.mkdir()
                link = root / ".claude" / "skills"
                link.parent.mkdir(parents=True)
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            try:
                with self.assertRaisesRegex(KitError, "project root"):
                    sync_project_skills(root)
                self.assertFalse((outside / "rtl-dv-kit").exists())
            finally:
                for child in outside.iterdir():
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                outside.rmdir()

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
