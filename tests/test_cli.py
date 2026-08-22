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
                "--task",
                "check APB",
                "--output",
                str(output),
                "--manifest",
                str(manifest),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("check APB", output.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["project"], "minimal_fixture")

    def test_check_requires_confirmation(self) -> None:
        result = self.run_cli("check", "--project-root", str(FIXTURE), "confirmed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires explicit confirmation", result.stderr)


if __name__ == "__main__":
    unittest.main()
