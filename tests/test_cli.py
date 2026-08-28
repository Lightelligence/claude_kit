from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_project"
ENTRY = ROOT / "bin" / "claude-kit"


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ENTRY), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_doctor_json(self) -> None:
        result = self.run_cli("doctor", "--project-root", str(FIXTURE), "--strict", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")

    def test_list_skills_and_evidence_check(self) -> None:
        skills = self.run_cli("list", "skills", "--json")
        self.assertEqual(skills.returncode, 0, skills.stderr)
        self.assertIn("rtl-design", {item["id"] for item in json.loads(skills.stdout)})
        skills_text = self.run_cli("list", "skills")
        self.assertEqual(skills_text.returncode, 0, skills_text.stderr)
        self.assertIn("rtl-design\tPlan and implement", skills_text.stdout)
        providers = self.run_cli("list", "providers", "--json")
        self.assertEqual(providers.returncode, 0, providers.stderr)
        self.assertEqual(json.loads(providers.stdout)[0]["id"], "xverif")
        evidence = self.run_cli(
            "evidence", "check", "--project-root", str(FIXTURE),
            "--file", "out/evidence.json", "--strict", "--json",
        )
        self.assertEqual(evidence.returncode, 0, evidence.stderr)
        self.assertEqual(json.loads(evidence.stdout)["status"], "passed")

    def test_xverif_docs_explain_vendor_environment_boundary(self) -> None:
        english = (ROOT / "docs" / "xverif-integration.md").read_text(encoding="utf-8")
        chinese = (ROOT / "docs" / "xverif-integration.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("ordinary Claude Code shell does not need to export", english)
        self.assertIn("explicit simulation is selected", english)
        self.assertIn("A separate `simmer` process cannot", english)
        self.assertIn("retroactively update", english)
        self.assertIn("does not auto-run a simulation", english)
        self.assertIn("普通 Claude Code shell 不需要手工 export", chinese)
        self.assertIn("显式选择 simulation", chinese)
        self.assertIn("单独启动的 `simmer` 进程不能回头更新", chinese)
        self.assertIn("不会为了准备环境而自动运行 simulation", chinese)

    def test_plan_routes_workflow_and_reports_gates(self) -> None:
        workflows = self.run_cli("list", "workflows", "--json")
        self.assertEqual(workflows.returncode, 0, workflows.stderr)
        self.assertIn("debug", {item["id"] for item in json.loads(workflows.stdout)})
        plan = self.run_cli(
            "plan",
            "--project-root", str(FIXTURE),
            "--task", "debug APB timeout in simulation",
            "--pack", "protocols.apb",
            "--json",
        )
        self.assertEqual(plan.returncode, 0, plan.stderr)
        payload = json.loads(plan.stdout)
        self.assertEqual(payload["workflow"]["id"], "debug")
        self.assertIn("debugger", payload["roles"])
        self.assertIn("source_revision", payload["missing_facts"])
        text_plan = self.run_cli(
            "plan",
            "--project-root", str(FIXTURE),
            "--task", "debug APB timeout in simulation",
        )
        self.assertEqual(text_plan.returncode, 0, text_plan.stderr)
        self.assertIn("checks: inspect(available)", text_plan.stdout)

    def test_checks_menu_and_multi_check_report(self) -> None:
        menu = self.run_cli("checks", "--project-root", str(FIXTURE), "--json")
        self.assertEqual(menu.returncode, 0, menu.stderr)
        menu_payload = json.loads(menu.stdout)
        inspect = next(item for item in menu_payload if item["name"] == "inspect")
        self.assertEqual(inspect["category"], "inspect")
        batch = self.run_cli(
            "check-batch",
            "--project-root", str(FIXTURE),
            "--check", "inspect",
            "--check", "confirmed",
            "--confirm",
        )
        self.assertEqual(batch.returncode, 0, batch.stderr)
        payload = json.loads(batch.stdout)
        self.assertEqual(payload["summary"]["passed"], 2)
        self.assertEqual(len(payload["results"]), 2)

    def test_artifact_read_is_bounded_and_project_relative(self) -> None:
        result = self.run_cli(
            "artifact", "read", "--project-root", str(FIXTURE),
            "--file", "out/logs/README.md", "--max-bytes", "4", "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["bytes"], len((FIXTURE / "out/logs/README.md").read_bytes()))
        self.assertTrue(payload["truncated"])
        self.assertEqual(len(payload["text"].encode("utf-8")), 4)

        rejected = self.run_cli(
            "artifact", "read", "--project-root", str(FIXTURE),
            "--file", "../README.md", "--json",
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("project root", rejected.stderr)

    def test_regression_artifact_commands_use_profile_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            regression = Path(directory) / "regression" / "checkout-a"
            shutil.copytree(FIXTURE, project)
            simulation = regression / "tb__vcs__smoke__7"
            simulation.mkdir(parents=True)
            log = simulation / "run.log"
            log.write_text("smoke result\n", encoding="utf-8")
            profile = project / ".ai" / "project.toml"
            profile.write_text(
                profile.read_text(encoding="utf-8")
                + f'\n[artifacts.regression]\nroot = "{str(regression).replace(chr(92), "/")}"\n',
                encoding="utf-8",
            )
            discovered = self.run_cli(
                "artifact", "discover", "--project-root", str(project),
                "--kind", "simulation", "--test", "smoke", "--run-id", "7", "--json",
            )
            self.assertEqual(discovered.returncode, 0, discovered.stderr)
            payload = json.loads(discovered.stdout)
            self.assertEqual(payload["match_count"], 1)
            self.assertEqual(payload["artifacts"][0]["primary_log"], str(log.resolve()))
            read = self.run_cli(
                "artifact", "read-regression", "--project-root", str(project),
                "--file", str(log), "--json",
            )
            self.assertEqual(read.returncode, 0, read.stderr)
            self.assertIn("smoke result", json.loads(read.stdout)["text"])

    def test_context_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            shutil.copytree(FIXTURE, project)
            output = project / "out" / "context.md"
            manifest = project / "out" / "manifest.json"
            result = self.run_cli(
                "context",
                "--project-root", str(project),
                "--role",
                "reviewer",
                "--pack",
                "protocols.apb",
                "--skill",
                "rtl-dv-context",
                "--task",
                "check APB",
                "--output",
                str(output),
                "--manifest",
                str(manifest),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("check APB", output.read_text(encoding="utf-8"))
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["project"], "minimal_fixture")
            self.assertEqual(manifest_payload["skills"], ["rtl-dv-context"])

    def test_task_file_is_project_relative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            shutil.copytree(FIXTURE, project)
            task_file = project / "docs" / "task.md"
            task_file.write_text("task from file", encoding="utf-8")
            result = self.run_cli(
                "context",
                "--project-root", str(project),
                "--task-file", str(task_file),
                "--role", "reviewer",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("task from file", result.stdout)

            outside = Path(directory) / "outside.md"
            outside.write_text("must not be read", encoding="utf-8")
            rejected = self.run_cli(
                "context",
                "--project-root", str(project),
                "--task-file", str(outside),
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("escapes project root", rejected.stderr)

    def test_check_requires_confirmation(self) -> None:
        result = self.run_cli("check", "--project-root", str(FIXTURE), "confirmed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires explicit confirmation", result.stderr)

    def test_adapter_check_is_optional(self) -> None:
        result = self.run_cli("adapter", "check", "--project-root", str(FIXTURE), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")

    def test_init_can_generate_optional_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            result = self.run_cli(
                "init", "--project-root", str(project),
                "--kit-path", "third_party/claude_kit", "--with-mcp",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
            server = config["mcpServers"]["claude-kit"]
            self.assertEqual(server["type"], "stdio")
            self.assertIn("mcp", server["args"])

    def test_init_template_includes_hw_as_writable_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            result = self.run_cli(
                "init", "--project-root", str(project), "--no-skills",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = tomllib.loads((project / ".ai" / "project.toml").read_text(encoding="utf-8"))
            self.assertEqual(profile["roots"]["hw"], ["hw"])
            self.assertIn("hw/**", profile["permissions"]["writable"])

    def test_init_no_skills_flag_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            result = self.run_cli(
                "init", "--project-root", str(project), "--no-skills",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            created = json.loads(result.stdout)["created"]
            self.assertNotIn(".claude/skills/rtl-dv-kit/SKILL.md", created)
            self.assertFalse((project / ".claude" / "skills").exists())


if __name__ == "__main__":
    unittest.main()
