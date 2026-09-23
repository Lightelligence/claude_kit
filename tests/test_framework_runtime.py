"""Runtime generation must honor a consumer's migrated or legacy launcher."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from claude_kit.core import resource_root


class FrameworkRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        config = self.root / '.claude'
        config.mkdir()
        (config / 'project.toml').write_text('schema_version = 1\n')
        (config / 'mcp-requirements.txt').write_text('mcp\nnumpy\nopenpyxl\npandas\npyyaml\nxlrd\n')
        scripts = resource_root() / 'framework/soc/.claude/scripts'
        spec = importlib.util.spec_from_file_location('framework_project', scripts / 'framework_project.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        with patch.dict(os.environ, {'PROJ_DIR': str(self.root)}), patch.dict(sys.modules, {'framework_project': helper}):
            spec = importlib.util.spec_from_file_location('runtime_layout_test', scripts / 'sync_mcp_runtime.py')
            self.sync = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.sync)

    def select(self, launcher):
        (self.root / '.claude/mcp-servers.json').write_text(json.dumps({
            'schema_version': 1, 'servers': [{'name': 'fixture'}], 'launcher': launcher}))

    def test_migrated_consumer_does_not_recreate_root_scripts(self):
        self.select('.claude/scripts/run_mcp_python.sh')
        self.sync.validate_inputs()
        self.assertEqual(self.sync.sync_runtime(write=True), 0)
        self.assertFalse((self.root / 'scripts').exists())
        runtime = self.root / '.claude/scripts/run_mcp_python.sh'
        self.assertEqual(runtime.read_text(), self.sync._runtime_launcher())
        self.assertTrue((runtime.parent / 'setup_mcp_env.sh').is_file())
        # A second generation must retain the same two outputs.
        self.assertEqual(self.sync.sync_runtime(write=True), 0)
        self.assertFalse((self.root / 'scripts').exists())

    def test_legacy_consumer_retains_its_forwarder(self):
        self.select('scripts/mcp_python.sh')
        self.sync.validate_inputs()
        self.sync.sync_runtime(write=True)
        self.assertEqual((self.root / 'scripts/mcp_python.sh').read_text(), self.sync._root_launcher())
        self.assertTrue((self.root / '.claude/scripts/run_mcp_python.sh').is_file())

    def test_unknown_launcher_is_rejected_before_generation(self):
        self.select('../elsewhere.sh')
        with self.assertRaises(ValueError):
            self.sync.validate_inputs()
        self.assertFalse((self.root / 'scripts').exists())

    def test_packaged_runtime_matches_its_generator(self):
        packaged = resource_root() / 'framework/soc/.claude/scripts/run_mcp_python.sh'
        self.assertEqual(packaged.read_text(), self.sync._runtime_launcher())

    @unittest.skipUnless(os.name == 'posix', 'POSIX MCP launchers')
    def test_optional_launchers_forward_arguments_without_live_services(self):
        scripts = resource_root() / 'framework/soc/.claude/scripts'
        fake = self.root / 'fake-executable'
        fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        fake.chmod(0o755)
        credentials = self.root / 'fixture.env'
        credentials.write_text('# Test fixture; no credentials required\n')
        env = dict(os.environ, HOME=str(self.root), MCP_ATLASSIAN_ENV_FILE=str(credentials),
                   MCP_ATLASSIAN_BIN=str(fake), XVERIF_HOME=str(self.root), XVERIF_PYTHON=str(fake))
        for name, expected in [('atlassian_mcp.sh', '--probe\n'),
                               ('xverif_mcp.sh', '-m\nxverif_mcp.server\n--probe\n')]:
            with self.subTest(launcher=name):
                result = subprocess.run(['bash', str(scripts / name), '--probe'], env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)
