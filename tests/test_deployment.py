import hashlib
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

    def write_manifest(self, content):
        directory = self.root / ".claude"
        directory.mkdir(exist_ok=True)
        path = directory / "kit-attachment.toml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_selective_manifest_uses_vendored_relative_links(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = ["reviewer"]
skills = ["rtl-design"]

[aliases.skills]
rtl = "rtl-design"

[aliases.roles]
project-reviewer = "reviewer"
''')
        result = attach_project(self.root, manifest=manifest.relative_to(self.root))
        self.assertEqual(result["manifest"], ".claude/kit-attachment.toml")
        self.assertEqual(result["profile"], None)
        self.assertEqual(result["skills"], ["rtl-design"])
        self.assertEqual(result["roles"], ["reviewer"])
        self.assertFalse((self.root / ".mcp.json").exists())
        self.assertFalse((self.root / ".claude/project.toml").exists())
        for name in ("rtl-design",):
            link = self.root / ".claude/skills" / name
            self.assertTrue(link.is_symlink())
            self.assertFalse(Path(os.readlink(link)).is_absolute())
            self.assertTrue(link.resolve().is_relative_to(vendored))
        alias = self.root / ".claude/skills/rtl/SKILL.md"
        self.assertTrue(alias.is_file())
        self.assertIn('name: "rtl"', alias.read_text())
        self.assertIn(
            "third_party/claude_kit/src/claude_kit/resources/skills/rtl-design/SKILL.md",
            alias.read_text(),
        )
        self.assertIn('name: "project-reviewer"', (self.root / ".claude/agents/project-reviewer.md").read_text())
        self.assertEqual(attach_project(self.root, manifest=manifest)["changed"], [])

    def test_vendored_manifest_uses_vendored_catalog(self):
        vendored = self.root / "third_party/claude_kit"
        resources = vendored / "src/claude_kit/resources"
        role = resources / "roles/vendored-reviewer.md"
        role.parent.mkdir(parents=True)
        role.write_text("---\nid: vendored-reviewer\n---\n# Vendored reviewer\n", encoding="utf-8")
        skill = resources / "skills/vendored-skill/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: vendored-skill\ndescription: Vendored only\n---\n", encoding="utf-8")
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = ["vendored-reviewer"]
skills = ["vendored-skill"]
''')
        result = attach_project(self.root, manifest=manifest)
        self.assertEqual(result["roles"], ["vendored-reviewer"])
        self.assertEqual(result["skills"], ["vendored-skill"])
        self.assertTrue((self.root / ".claude/agents/kit-vendored-reviewer.md").is_file())
        self.assertEqual((self.root / ".claude/skills/vendored-skill").resolve(), skill.parent)

    def test_vendored_role_wrapper_uses_catalog_summary(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = ["crg-engineer"]
skills = []
''')
        attach_project(self.root, manifest=manifest)
        wrapper = (self.root / ".claude/agents/kit-crg-engineer.md").read_text()
        self.assertIn(
            'description: "Generate clock/reset RTL and constraints from approved requirements through a registered project generator."',
            wrapper,
        )
        self.assertIn(
            "`third_party/claude_kit/src/claude_kit/resources/roles/crg-engineer.md`",
            wrapper,
        )

    def test_manifest_can_disable_only_mcp_management(self):
        manifest = self.write_manifest('''schema_version = 1
manage_mcp = false
roles = []
skills = []
''')
        result = attach_project(self.root, manifest=manifest)
        self.assertIn(".claude/project.toml", result["changed"])
        self.assertTrue((self.root / ".claude/project.toml").is_file())
        self.assertFalse((self.root / ".mcp.json").exists())

    def test_manifest_rejects_unknown_ids_and_duplicate_targets(self):
        unknown = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = ["missing"]
skills = []
''')
        with self.assertRaisesRegex(KitError, "Unknown role"):
            attach_project(self.root, manifest=unknown)
        duplicate = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = ["rtl-design"]
[aliases.skills]
rtl-design = "rtl-design"
''')
        with self.assertRaisesRegex(KitError, "Duplicate attachment target"):
            attach_project(self.root, manifest=duplicate)

    def test_manifest_rejects_unknown_skill_and_invalid_alias(self):
        unknown = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = ["missing"]
''')
        with self.assertRaisesRegex(KitError, "Unknown skill"):
            attach_project(self.root, manifest=unknown)
        invalid_names = [
            "../outside",
            "bad name",
            "bad: name",
            "bad\\\\name",
            "bad/name",
            "bad\\nname",
            "-leading",
            "trailing.",
            "CON",
            "con.txt",
            "NUL",
            "COM1",
            "lpt9.log",
        ]
        for name in invalid_names:
            with self.subTest(name=name):
                invalid_alias = self.write_manifest(f'''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = []
[aliases.skills]
{json.dumps(name)} = "rtl-design"
''')
                with self.assertRaisesRegex(KitError, "Invalid attachment alias"):
                    attach_project(self.root, manifest=invalid_alias)

    def test_manifest_rejects_case_insensitive_alias_collisions(self):
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = []
[aliases.skills]
Foo = "rtl-design"
foo = "rtl-design"
''')
        with self.assertRaisesRegex(KitError, "Duplicate attachment alias"):
            attach_project(self.root, manifest=manifest)

    def test_manifest_rejects_malformed_toml_and_invalid_kit_path(self):
        malformed = self.write_manifest("schema_version = [")
        with self.assertRaisesRegex(KitError, "Cannot read attachment manifest"):
            attach_project(self.root, manifest=malformed)
        missing = self.write_manifest('''schema_version = 1
kit_path = "third_party/missing"
roles = []
skills = []
''')
        with self.assertRaisesRegex(KitError, "Vendored kit path does not exist"):
            attach_project(self.root, manifest=missing)
        outside = Path(self.temp.name) / "kit"
        outside.mkdir()
        escaped = self.write_manifest(f'''schema_version = 1
kit_path = {json.dumps(str(outside))}
roles = []
skills = []
''')
        with self.assertRaisesRegex(KitError, "Invalid attachment path"):
            attach_project(self.root, manifest=escaped)

    def test_vendored_resources_cannot_escape_kit_root(self):
        vendored = self.root / "third_party/claude_kit"
        resources_parent = vendored / "src/claude_kit"
        resources_parent.mkdir(parents=True)
        outside = Path(self.temp.name) / "outside-resources"
        outside.mkdir()
        (resources_parent / "resources").symlink_to(outside, target_is_directory=True)
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = []
skills = []
''')
        with self.assertRaisesRegex(KitError, "resources escape"):
            attach_project(self.root, manifest=manifest)

    def test_vendored_skill_files_cannot_escape_skill_root(self):
        vendored = self.root / "third_party/claude_kit"
        resources = vendored / "src/claude_kit/resources"
        skill = resources / "skills/escaped/SKILL.md"
        skill.parent.mkdir(parents=True)
        outside = Path(self.temp.name) / "outside-skill.md"
        outside.write_text(
            "---\nname: escaped\ndescription: Outside skill\n---\n",
            encoding="utf-8",
        )
        skill.symlink_to(outside)
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = []
skills = ["escaped"]
''')
        with self.assertRaisesRegex(KitError, "Skill escaped escapes kit resources"):
            attach_project(self.root, manifest=manifest)

    def test_vendored_mcp_uses_vendored_launcher(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        launcher = vendored / "bin/claude-kit"
        launcher.parent.mkdir()
        launcher.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        manifest = self.write_manifest('''schema_version = 1
kit_path = "third_party/claude_kit"
roles = []
skills = []
''')
        attach_project(self.root, manifest=manifest)
        server = json.loads((self.root / ".mcp.json").read_text())["mcpServers"]["claude-kit"]
        self.assertEqual(server["command"], "third_party/claude_kit/bin/claude-kit")
        self.assertNotEqual(server["command"], "claude-kit")

    def test_vendored_mcp_requires_vendored_launcher(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        manifest = self.write_manifest('''schema_version = 1
kit_path = "third_party/claude_kit"
roles = []
skills = []
''')
        with self.assertRaisesRegex(KitError, "requires bin/claude-kit"):
            attach_project(self.root, manifest=manifest)

    def test_duplicate_and_invalid_catalog_ids_are_rejected(self):
        duplicate_roles = [
            {"id": "same", "path": "roles/one.md"},
            {"id": "same", "path": "roles/two.md"},
        ]
        with patch("claude_kit.deployment.role_catalog", return_value=duplicate_roles):
            with self.assertRaisesRegex(KitError, "Duplicate role ID"):
                attach_project(self.root)
        invalid_skills = [{"id": "bad/name", "path": "skills/bad/SKILL.md"}]
        with patch("claude_kit.deployment.skill_catalog", return_value=invalid_skills):
            with self.assertRaisesRegex(KitError, "Invalid skill ID"):
                attach_project(self.root)

    def test_manifest_accepts_legacy_attachment_state(self):
        state = self.root / ".claude/kit-state.json"
        state.parent.mkdir()
        state.write_text(json.dumps({"schema_version": 1, "managed": {}}))
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = ["rtl-design"]
''')
        result = attach_project(self.root, manifest=manifest)
        self.assertEqual(result["status"], "passed")
        self.assertTrue((self.root / ".claude/skills/rtl-design").is_symlink())

    def test_manifest_rejects_escape_and_unmanaged_conflict(self):
        outside = Path(self.temp.name) / "outside.toml"
        outside.write_text("schema_version = 1")
        with self.assertRaisesRegex(KitError, "inside the project root"):
            attach_project(self.root, manifest=outside)
        conflict = self.root / ".claude/skills/rtl-design"
        conflict.mkdir(parents=True)
        (conflict / "SKILL.md").write_text("project owned")
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = ["rtl-design"]
''')
        with self.assertRaisesRegex(KitError, "conflicts"):
            attach_project(self.root, manifest=manifest)

    def test_skill_alias_rejects_unmanaged_support_files(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        helper = self.root / ".claude/skills/rtl/project_helper.py"
        helper.parent.mkdir(parents=True)
        helper.write_text("project owned", encoding="utf-8")
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = []
skills = []
[aliases.skills]
rtl = "rtl-design"
''')
        with self.assertRaisesRegex(KitError, "directory conflicts"):
            attach_project(self.root, manifest=manifest)
        self.assertEqual(helper.read_text(encoding="utf-8"), "project owned")
        self.assertFalse((helper.parent / "SKILL.md").exists())

    def test_skill_alias_rejects_regular_file_at_alias_path(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        alias_path = self.root / ".claude/skills/rtl"
        alias_path.parent.mkdir(parents=True)
        alias_path.write_text("project owned", encoding="utf-8")
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = []
skills = []
[aliases.skills]
rtl = "rtl-design"
''')
        with self.assertRaisesRegex(KitError, "path conflicts"):
            attach_project(self.root, manifest=manifest)
        self.assertEqual(alias_path.read_text(encoding="utf-8"), "project owned")

    def test_alias_state_without_ownership_marker_cannot_overwrite_project_file(self):
        vendored = self.root / "third_party/claude_kit"
        shutil.copytree(Path(__file__).resolve().parents[1] / "src", vendored / "src")
        target = self.root / ".claude/agents/project-reviewer.md"
        target.parent.mkdir(parents=True)
        original = "project owned\n"
        target.write_text(original, encoding="utf-8")
        state = target.parent.parent / "kit-state.json"
        fingerprint = "sha256:" + hashlib.sha256(original.encode("utf-8")).hexdigest()
        state.write_text(json.dumps({
            "schema_version": 1,
            "managed": {".claude/agents/project-reviewer.md": fingerprint},
        }))
        manifest = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
kit_path = "third_party/claude_kit"
roles = []
skills = []
[aliases.roles]
project-reviewer = "reviewer"
''')
        with self.assertRaisesRegex(KitError, "conflicts"):
            attach_project(self.root, manifest=manifest)
        self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_manifest_symlink_loops_are_reported_as_kit_errors(self):
        first = self.root / "first.toml"
        second = self.root / "second.toml"
        first.symlink_to(second.name)
        second.symlink_to(first.name)
        with self.assertRaisesRegex(KitError, "manifest does not exist"):
            attach_project(self.root, manifest=first)

    def test_manifest_reports_retired_resources_without_deleting(self):
        first = self.write_manifest('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = ["rtl-design"]
''')
        attach_project(self.root, manifest=first)
        first.write_text('''schema_version = 1
manage_profile = false
manage_mcp = false
roles = []
skills = []
''')
        result = attach_project(self.root, manifest=first)
        relative = ".claude/skills/rtl-design"
        self.assertIn(relative, result["retired_managed_paths"])
        self.assertTrue((self.root / relative).is_symlink())

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

    def test_attachment_does_not_remove_replacement_lock(self):
        lock = self.root / ".claude-kit-attach.lock"

        def replace_lock(root, *, dry_run=False, manifest=None):
            lock.unlink()
            lock.write_text("replacement", encoding="utf-8")
            return {"status": "passed"}

        with patch("claude_kit.deployment._attach_project", side_effect=replace_lock):
            result = attach_project(self.root)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(lock.read_text(encoding="utf-8"), "replacement")

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
    def test_new_generated_files_use_normal_modes(self):
        attach_project(self.root)
        generated = [
            self.root / ".claude/project.toml",
            self.root / ".mcp.json",
            self.root / ".claude/kit-state.json",
            self.root / f".claude/agents/kit-{role_catalog()[0]['id']}.md",
        ]
        for path in generated:
            with self.subTest(path=path):
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)

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
            self.assertIn(f'name: "kit-{entry["id"]}"', native.read_text())
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

    def test_new_mcp_uses_runtime_root_without_rewriting_legacy_entry(self):
        attach_project(self.root)
        path = self.root / ".mcp.json"
        config = json.loads(path.read_text())
        server = config["mcpServers"]["claude-kit"]
        self.assertEqual(server["args"], ["mcp", "serve", "--profile", ".claude/project.toml"])
        server["args"][2:2] = ["--project-root", "."]
        path.write_text(json.dumps(config))
        original = path.read_bytes()
        self.assertEqual(attach_project(self.root)["changed"], [])
        self.assertEqual(path.read_bytes(), original)

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

    def test_interrupted_transaction_rolls_back_every_change(self):
        replace = os.replace

        def interrupt_on_state(source, target):
            if Path(target).name == "kit-state.json":
                raise KeyboardInterrupt()
            return replace(source, target)

        with patch("claude_kit.deployment.os.replace", side_effect=interrupt_on_state):
            with self.assertRaises(KeyboardInterrupt):
                attach_project(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

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
