import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

from claude_kit.core import KitError, resource_root
from claude_kit.deployment import attach_project


class FrameworkTests(unittest.TestCase):
    def project(self, path, extra=''):
        (path / '.claude').mkdir(parents=True)
        (path / '.claude/kit-attachment.toml').write_text(
            'schema_version = 1\nmanage_profile = false\nmanage_mcp = false\n'
            'roles = []\nskills = []\nframework = "soc"\n' + extra)
        (path / '.claude/project.toml').write_text('schema_version = 1\n[project]\nid = "fixture"\n')
        return path

    def test_two_projects_share_sources_and_keep_own_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            projects = [self.project(Path(temp) / name) for name in ('one', 'two')]
            for i, root in enumerate(projects):
                (root / '.claude/soc-lsp.json').write_text(json.dumps({'bazel_target': f'//benches/p{i}:bench'}))
                first = attach_project(root, manifest='.claude/kit-attachment.toml')
                self.assertEqual(first['status'], 'passed')
                self.assertEqual(attach_project(root, manifest='.claude/kit-attachment.toml')['changed'], [])
                self.assertFalse((root / '.mcp.json').exists())
                self.assertEqual(json.loads((root / '.claude/soc-lsp.json').read_text())['bazel_target'], f'//benches/p{i}:bench')
                for rel in ('.claude/agents/soc-reviewer.md', '.claude/scripts/dv_log_evidence.py', '.claude/skills/soc-lsp/mcp_server.py'):
                    self.assertTrue((root / rel).is_symlink())
                    cross_drive = root.resolve().drive.casefold() != resource_root().resolve().drive.casefold()
                    self.assertEqual(os.path.isabs(os.readlink(root / rel)), cross_drive)
            self.assertEqual((projects[0] / '.claude/scripts/dv_log_evidence.py').resolve(),
                             (projects[1] / '.claude/scripts/dv_log_evidence.py').resolve())

    def test_conflict_preflight_and_explicit_project_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(Path(temp))
            target = root / '.claude/rules/04_coding_style.md'
            target.parent.mkdir()
            target.write_text('project-specific rule')
            with self.assertRaises(KitError):
                attach_project(root, manifest='.claude/kit-attachment.toml')
            self.assertFalse((root / '.claude/scripts').exists())
            manifest = root / '.claude/kit-attachment.toml'
            manifest.write_text(manifest.read_text() + 'framework_exclude = [".claude/rules/04_coding_style.md"]\n')
            attach_project(root, manifest='.claude/kit-attachment.toml')
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.read_text(), 'project-specific rule')

    def test_unknown_exclusion_fails_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(Path(temp), 'framework_exclude = ["../escape"]\n')
            with self.assertRaises(KitError):
                attach_project(root, manifest='.claude/kit-attachment.toml')
            self.assertFalse((root / '.claude/agents').exists())

    def test_framework_and_catalog_overlap_fails_before_writes(self):
        for identifier in ('xwiki', 'rtl-dv-kit'):
            with self.subTest(skill=identifier), tempfile.TemporaryDirectory() as temp:
                root = self.project(Path(temp))
                manifest = root / '.claude/kit-attachment.toml'
                manifest.write_text(manifest.read_text().replace('skills = []', f'skills = ["{identifier}"]'))
                with patch('claude_kit.deployment.os.replace') as replace:
                    with self.assertRaisesRegex(KitError, 'Overlapping attachment targets'):
                        attach_project(root, manifest=manifest)
                    replace.assert_not_called()
                self.assertFalse((root / '.claude/skills').exists())
                self.assertFalse((root / '.claude/agents').exists())

    def test_framework_cross_volume_links_fall_back_to_absolute(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(Path(temp))
            with patch('claude_kit.deployment.os.path.relpath', side_effect=ValueError('different drives')):
                result = attach_project(root, manifest='.claude/kit-attachment.toml')
                self.assertEqual(attach_project(root, manifest='.claude/kit-attachment.toml')['changed'], [])
            self.assertEqual(result['status'], 'passed')
            target = root / '.claude/agents/soc-reviewer.md'
            self.assertTrue(Path(os.readlink(target)).is_absolute())
            self.assertTrue(target.is_file())

    def test_project_resolution_uses_consumer_and_rejects_stale_environment(self):
        helper = resource_root() / 'framework/soc/.claude/scripts/framework_project.py'
        spec = importlib.util.spec_from_file_location('framework_root_test', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(Path(temp))
            with patch.dict(os.environ, {'PROJ_DIR': str(root)}):
                self.assertEqual(module.project_root(), root.resolve())
            with patch.dict(os.environ, {'PROJ_DIR': str(root / 'missing')}):
                with self.assertRaises(ValueError):
                    module.project_root()

    def test_import_budget_counts_shared_text_and_rejects_escape(self):
        helper = resource_root() / 'framework/soc/.claude/scripts/framework_project.py'
        spec = importlib.util.spec_from_file_location('framework_memory_test', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'CLAUDE.md').write_text('@shared.md\n')
            (root / 'shared.md').write_text('shared instructions\n@CLAUDE.md\n')
            self.assertEqual(module.instruction_text(root / 'CLAUDE.md', root).count('shared instructions'), 1)
            (root / 'shared.md').write_text('```python\n@mcp.tool()\n```\n')
            self.assertIn('@mcp.tool()', module.instruction_text(root / 'CLAUDE.md', root))
            (root / 'sample.py').write_text('@mcp.tool()\n')
            self.assertEqual(module.instruction_text(root / 'sample.py', root), '@mcp.tool()\n')
            (root / 'shared.md').write_text('@../outside.md\n')
            with self.assertRaises((ValueError, FileNotFoundError)):
                module.instruction_text(root / 'CLAUDE.md', root)

    def test_role_sync_cannot_write_through_shared_link(self):
        scripts = resource_root() / 'framework/soc/.claude/scripts'
        spec = importlib.util.spec_from_file_location('framework_project', scripts / 'framework_project.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(Path(temp))
            source = root / 'common.md'
            source.write_text('shared original')
            alias = root / '.claude/agents/shared.md'
            alias.parent.mkdir()
            alias.symlink_to(source)
            with patch.dict(os.environ, {'PROJ_DIR': str(root)}), patch.dict(sys.modules, {'framework_project': helper}):
                spec = importlib.util.spec_from_file_location('role_sync_test', scripts / 'sync_agent_profiles.py')
                sync = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(sync)
                with patch.object(sync, 'expected', return_value={alias: 'unwanted edit'}):
                    with self.assertRaises(ValueError):
                        sync.run(write=True)
            self.assertEqual(source.read_text(), 'shared original')
            self.assertTrue(alias.is_symlink())
