import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_kit.core import KitError, _front_matter, discover_profile, doctor, find_project_root, resource_root, role_catalog, skill_catalog
from claude_kit.deployment import attach_project


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "example-project"
        self.root.mkdir()

    def test_dry_run_has_no_side_effects(self):
        result = attach_project(self.root, dry_run=True)
        self.assertEqual(result["status"], "planned")
        self.assertIn(".claude/project.toml", result["changed"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_folded_skill_descriptions_are_not_yaml_markers(self):
        entries = {entry["id"]: entry for entry in skill_catalog()}
        for name in ("xwiki", "xverif", "xverif-admin"):
            self.assertGreater(len(entries[name]["description"]), 30)
            self.assertNotIn(entries[name]["description"], (">", "|"))
        source = self.root / "SKILL.md"
        source.write_text('---\nname: example\ndescription: >-\n  first: detail\n  second line\nversion: 2\n---\n')
        self.assertEqual(_front_matter(source)["description"], "first: detail second line")
        self.assertEqual(_front_matter(source)["version"], "2")

    def test_existing_attachment_lock_is_preserved(self):
        lock = self.root / ".claude-kit-attach.lock"
        lock.write_text("owned by another process")
        with self.assertRaisesRegex(KitError, "Another attachment"):
            attach_project(self.root)
        self.assertEqual(lock.read_text(), "owned by another process")
        self.assertEqual(list(self.root.iterdir()), [lock])

    def test_role_source_cannot_escape_resources(self):
        foreign = Path(self.temp.name) / "foreign.md"
        foreign.write_text("not a kit role")
        with patch("claude_kit.deployment.role_catalog", return_value=[{"id": "foreign", "path": str(foreign)}]):
            with self.assertRaisesRegex(KitError, "Role escapes"):
                attach_project(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cross_volume_links_fall_back_to_absolute_paths(self):
        with patch("claude_kit.deployment.os.path.relpath", side_effect=ValueError("different drives")):
            attach_project(self.root)
        for entry in skill_catalog():
            target = os.readlink(self.root / ".claude/skills" / entry["id"])
            self.assertTrue(Path(target).is_absolute())

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_windows_junction_parent_is_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.root / ".claude"), str(outside)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.assertRaises(KitError):
            attach_project(self.root)
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX file modes")
    def test_existing_config_mode_is_preserved(self):
        path = self.root / ".mcp.json"
        path.write_text('{"mcpServers":{}}')
        path.chmod(0o640)
        attach_project(self.root)
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    @unittest.skipIf(os.name == "nt", "POSIX interpreter shim")
    def test_interpreter_shim_handoff_is_bounded(self):
        shim = self.root / "python-shim"
        import shlex
        shim.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
        shim.chmod(0o755)
        env = os.environ.copy()
        env["CLAUDE_KIT_PYTHON"] = str(shim)
        entry = Path(__file__).resolve().parents[1] / "bin/claude-kit"
        result = subprocess.run([sys.executable, str(entry), "version"], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("version", json.loads(result.stdout))

    def test_attach_links_every_skill_and_resolves_support_files(self):
        result = attach_project(self.root)
        self.assertEqual(result["functional_validation"], "not_run")
        self.assertFalse((self.root / ".ai").exists())
        self.assertFalse((self.root / ".agents").exists())
        for entry in skill_catalog():
            linked = self.root / ".claude/skills" / entry["id"]
            original = (resource_root() / entry["path"]).parent
            self.assertTrue(linked.is_symlink())
            for source in original.rglob("*"):
                if source.is_file() and "__pycache__" not in source.parts:
                    self.assertEqual((linked / source.relative_to(original)).read_bytes(), source.read_bytes())
        for entry in role_catalog():
            native = self.root / f".claude/agents/kit-{entry['id']}.md"
            self.assertIn(f"name: kit-{entry['id']}", native.read_text())
            self.assertIn((resource_root() / entry["path"]).as_posix(), native.read_text())
        self.assertEqual(doctor(self.root)["status"], "passed")
        self.assertEqual(attach_project(self.root)["changed"], [])

    def test_preserves_other_mcp_settings_and_project_profile(self):
        config = {"mcpServers": {"xverif": {"command": "existing-wrapper"}, "drawio": {"type": "http", "url": "https://example.invalid/mcp"}}, "project_extra": True}
        (self.root / ".mcp.json").write_text(json.dumps(config))
        directory = self.root / ".claude"
        directory.mkdir()
        (directory / "settings.json").write_text('{"permissions":{"deny":["Write"]}}')
        (directory / "project.toml").write_text('schema_version=1\n[project]\nid="custom"\n')
        originals = {path: path.read_bytes() for path in directory.iterdir()}
        attach_project(self.root)
        result = json.loads((self.root / ".mcp.json").read_text())
        for name, server in config["mcpServers"].items():
            self.assertEqual(result["mcpServers"][name], server)
        self.assertTrue(result["project_extra"])
        for path, value in originals.items():
            self.assertEqual(path.read_bytes(), value)
        self.assertEqual(attach_project(self.root)["changed"], [])

    def test_legacy_profile_remains_authoritative_if_no_native_profile(self):
        (self.root / ".ai").mkdir()
        profile = self.root / ".ai/project.toml"
        profile.write_text('schema_version=1\n[project]\nid="legacy"\n')
        attach_project(self.root)
        self.assertEqual(discover_profile(self.root), profile)
        self.assertFalse((self.root / ".claude/project.toml").exists())
        self.assertIn(".ai/project.toml", json.loads((self.root / ".mcp.json").read_text())["mcpServers"]["claude-kit"]["args"])

    def test_conflicting_mcp_fails_before_creating_anything(self):
        path = self.root / ".mcp.json"
        path.write_text('{"mcpServers":{"claude-kit":{"command":"custom"}}}')
        original = path.read_bytes()
        with self.assertRaisesRegex(KitError, "MCP definition differs"):
            attach_project(self.root)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_existing_skill_directory_is_not_replaced(self):
        path = self.root / ".claude/skills" / skill_catalog()[0]["id"]
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text("project customization")
        with self.assertRaisesRegex(KitError, "conflicts"):
            attach_project(self.root)
        self.assertFalse((self.root / ".mcp.json").exists())
        self.assertEqual((path / "SKILL.md").read_text(), "project customization")

    def test_modified_native_role_is_not_overwritten(self):
        attach_project(self.root)
        role = self.root / f".claude/agents/kit-{role_catalog()[0]['id']}.md"
        role.write_text("project customization")
        with self.assertRaisesRegex(KitError, "conflicts"):
            attach_project(self.root)
        self.assertEqual(role.read_text(), "project customization")

    def test_parent_symlinks_are_rejected_without_following_them(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.root / ".claude").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(KitError, "real directory"):
            attach_project(self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_discovered_profile_cannot_escape_project(self):
        outside = Path(self.temp.name) / "outside.toml"
        outside.write_text("schema_version=1")
        (self.root / ".claude").mkdir()
        (self.root / ".claude/project.toml").symlink_to(outside)
        with self.assertRaisesRegex(KitError, "outside"):
            discover_profile(self.root)

    def test_native_profile_root_discovery_and_precedence(self):
        (self.root / ".claude").mkdir()
        native = self.root / ".claude/project.toml"
        native.write_text("schema_version=1")
        (self.root / ".ai").mkdir()
        (self.root / ".ai/project.toml").write_text("schema_version=1")
        child = self.root / "a/b"
        child.mkdir(parents=True)
        self.assertEqual(find_project_root(child), self.root)
        self.assertEqual(discover_profile(self.root), native)

    def test_failed_transaction_rolls_back_merged_config(self):
        original = b'{"mcpServers":{"external":{"command":"keep"}}}'
        path = self.root / ".mcp.json"
        path.write_bytes(original)
        if os.name != "nt":
            path.chmod(0o640)
        replace = os.replace

        def fail_state(source, target):
            if Path(target).name == "kit-state.json":
                raise OSError("injected storage failure")
            return replace(source, target)

        with patch("claude_kit.deployment.os.replace", side_effect=fail_state):
            with self.assertRaisesRegex(KitError, "rolled back"):
                attach_project(self.root)
        self.assertEqual(path.read_bytes(), original)
        if os.name != "nt":
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_relocation_updates_only_unchanged_managed_links(self):
        attach_project(self.root)
        copy = Path(self.temp.name) / "relocated-resources"
        shutil.copytree(resource_root(), copy)
        with patch("claude_kit.deployment.resource_root", return_value=copy):
            result = attach_project(self.root)
        self.assertTrue(result["changed"])
        for entry in skill_catalog():
            self.assertTrue((self.root / ".claude/skills" / entry["id"]).resolve().is_relative_to(copy))


if __name__ == "__main__":
    unittest.main()
