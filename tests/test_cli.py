from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
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
        evidence = self.run_cli(
            "evidence", "check", "--project-root", str(FIXTURE),
            "--file", "out/evidence.json", "--strict", "--json",
        )
        self.assertEqual(evidence.returncode, 0, evidence.stderr)
        self.assertEqual(json.loads(evidence.stdout)["status"], "passed")

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
