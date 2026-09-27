from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_kit.cli import main
from claude_kit.core import KitError, resource_root
from claude_kit.deployment import attach_project
from claude_kit.tool_audit import audit_project, render_audit
from claude_kit.tool_profiles import ToolProfileError, select_tool_profile


class ToolAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "project"
        self.root.mkdir()

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return path

    def fixture(self):
        secret = {"command": "private-command", "args": ["secret-arg"],
                  "env": {"TOKEN": "secret-env"}, "url": "https://secret.invalid",
                  "headers": {"Authorization": "secret-header"}}
        self.write(".mcp.json", {"mcpServers": {"kit": secret, "drift": {"command": "old"}, "legacy": {}}})
        self.write(".claude/mcp-catalog.json", {"mcpServers": {
            "kit": secret, "same-kit": secret, "different-env": {**secret, "env": {"TOKEN": "other"}},
            "debugger": {"command": "debug-command"}, "drift": {"command": "new"}}})
        self.write(".claude/tool-profiles.json", {"schema_version": 1,
            "mcp_config": ".claude/mcp-catalog.json",
            "profiles": {"debug": {"description": "secret-description", "servers": ["kit", "debugger"]}}})

    def test_selection_drift_duplicates_and_no_execution_or_mutation(self):
        self.fixture()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch("subprocess.run", side_effect=AssertionError("must not execute")), patch("subprocess.Popen", side_effect=AssertionError("must not execute")):
            result = audit_project(self.root, "debug")
        servers = {s["name"]: s for s in result["servers"]}
        self.assertEqual(servers["debugger"]["placement"], "on_demand")
        self.assertEqual(servers["same-kit"]["placement"], "unassigned")
        self.assertTrue(servers["kit"]["selected"])
        self.assertFalse(servers["legacy"]["selected"])
        findings = {f["code"]: f for f in result["findings"]}
        self.assertEqual(findings["default_catalog_drift"]["names"], ["drift"])
        self.assertEqual(findings["default_missing_from_catalog"]["names"], ["legacy"])
        self.assertEqual(findings["identical_server_definitions"]["names"], ["kit", "same-kit"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        for report in (json.dumps(result), render_audit(result)):
            for hidden in ("private-command", "secret-arg", "secret-env", "secret.invalid", "secret-header", "secret-description", "debug-command"):
                self.assertNotIn(hidden, report)

    def test_settings_report_declarations_not_effective_state(self):
        self.fixture()
        self.write(".claude/settings.json", {"enabledPlugins": {"dv@market": True},
                   "hooks": {"PreToolUse": [{"hooks": [{"command": "secret-hook"}]}]},
                   "disabledMcpjsonServers": ["kit"]})
        self.write(".claude/settings.local.json", {"enabledPlugins": {"dv@market": False}})
        result = audit_project(self.root, "debug")
        self.assertFalse(result["runtime_verified"])
        self.assertEqual([p["enabled_declared"] for p in result["plugin_declarations"]], [True, False])
        self.assertEqual(result["mcp_disable_declarations"], [{"name": "kit", "source": ".claude/settings.json"}])
        self.assertTrue(next(s for s in result["servers"] if s["name"] == "kit")["selected"])
        self.assertNotIn("secret-hook", json.dumps(result))

    def test_skills_inventory_and_duplicate_candidates(self):
        body = "---\nname: same\ndescription: private-description\ndisable-model-invocation: true\n---\nprivate-body\n"
        first = self.write(".claude/skills/a/SKILL.md", body)
        self.write(".claude/skills/b/SKILL.md", body)
        self.write(".claude/skills/c/SKILL.md", body.replace("private-body", "different-body"))
        self.write(".claude/skills/a/references/huge.md", "x" * 1_000_001)
        (self.root / ".claude/skills/missing").mkdir()
        self.write(".claude/rules/rule.md", "private-rule")
        self.write(".claude/agents/agent.md", "private-agent")
        self.write("CLAUDE.md", "private-instructions")
        result = audit_project(self.root)
        self.assertEqual(result["summary"]["skills_present"], 3)
        self.assertEqual(result["skills"][0]["bytes"], len(first.read_bytes()))
        self.assertTrue(result["skills"][0]["manual_only_declared"])
        findings = {f["code"]: f for f in result["findings"]}
        self.assertEqual(len(findings["identical_skill_entrypoints"]["paths"]), 2)
        self.assertEqual(len(findings["duplicate_skill_names"]["paths"]), 3)
        self.assertIn("missing_skill_entrypoint", findings)
        self.assertEqual(result["summary"]["rules"], 1)
        self.assertEqual(result["summary"]["agents"], 1)
        self.assertNotIn("private-", json.dumps(result))

    @unittest.skipIf(os.name == "nt", "symlink privileges vary on Windows")
    def test_shared_skill_link_and_broken_link(self):
        shared = self.root.parent / "shared"
        shared.mkdir()
        (shared / "SKILL.md").write_text("---\nname: shared\n---\n", encoding="utf-8")
        skills = self.root / ".claude/skills"
        skills.mkdir(parents=True)
        (skills / "shared").symlink_to(shared, target_is_directory=True)
        (skills / "broken").symlink_to(self.root / "missing", target_is_directory=True)
        result = audit_project(self.root)
        self.assertTrue(result["skills"][1]["linked"])
        self.assertEqual(result["skills"][0]["status"], "missing_entrypoint")

    def test_empty_project_is_not_runtime_clean_bill(self):
        result = audit_project(self.root)
        self.assertEqual(result["summary"]["selected_servers"], 0)
        self.assertFalse(result["runtime_verified"])
        self.assertTrue(result["limitations"])
        with self.assertRaisesRegex(KitError, "Unknown tool profile"):
            audit_project(self.root, "debug")

    def test_default_inventory_without_profiles(self):
        self.write(".mcp.json", {"mcpServers": {"one": {}}})
        result = audit_project(self.root)
        self.assertEqual(result["summary"]["selected_servers"], 1)
        self.assertEqual(result["findings"][0]["code"], "no_task_profiles")

    def test_invalid_and_oversized_configs_are_rejected(self):
        for value in ("{", '{"mcpServers":{},"mcpServers":{}}', {"mcpServers": []}):
            with self.subTest(value=value):
                self.write(".mcp.json", value)
                with self.assertRaises((KitError, ToolProfileError)):
                    audit_project(self.root)
        self.write(".mcp.json", " " * 1_000_001)
        with self.assertRaisesRegex(KitError, "exceeds 1 MB"):
            audit_project(self.root)

    def test_catalog_traversal_is_rejected(self):
        self.write(".claude/tool-profiles.json", {"mcp_config": "../outside.json"})
        with self.assertRaisesRegex(KitError, "project-relative"):
            audit_project(self.root)

    def test_cli_json_markdown_and_unknown_profile(self):
        self.fixture()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["tool-audit", "--project-root", str(self.root), "--tools", "debug"]), 0)
        self.assertEqual(json.loads(output.getvalue())["summary"]["selected_servers"], 2)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["tool-audit", "--project-root", str(self.root), "--format", "markdown"]), 0)
        self.assertIn("runtime loading has not been verified", output.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["tool-audit", "--project-root", str(self.root), "--tools", "unknown"]), 2)

    @unittest.skipIf(os.name == "nt", "attachment uses directory symlinks")
    def test_minimal_templates_work_with_pinned_submodule(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        templates = resource_root() / "templates"
        manifest = self.write(".claude/kit-attachment.toml", (templates / "kit-attachment.dv-minimal.toml").read_text())
        attached = attach_project(self.root, manifest=manifest)
        self.assertEqual(len(attached["skills"]), 4)
        self.assertEqual(attached["roles"], [])
        self.assertFalse((self.root / ".mcp.json").exists())
        profiles = json.loads((templates / "tool-profiles.dv-minimal.json").read_text())
        self.write(".claude/tool-profiles.json", profiles)
        names = {s for p in profiles["profiles"].values() for s in p["servers"]}
        self.write(".claude/mcp-catalog.json", {"mcpServers": {n: {"command": n} for n in names}})
        self.assertEqual(len(select_tool_profile(self.root, "daily")["mcpServers"]), 3)
        self.assertEqual(audit_project(self.root, "debug")["summary"]["skills_present"], 4)


if __name__ == "__main__":
    unittest.main()
