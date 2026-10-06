import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from claude_kit.core import KitError
from claude_kit.mcp_server import _call_tool, _tool_definitions


class ArtifactSearchInterfaces(unittest.TestCase):
    def test_mcp_exposes_batch_search_without_execution_permission(self):
        for profile in ('compact', 'full'):
            tools = {t['name']: t for t in _tool_definitions(False, profile)}
            self.assertIn('search_artifact', tools)
            self.assertNotIn('run_check', tools)
            self.assertEqual(tools['search_artifact']['inputSchema']['required'], ['path', 'queries'])

    def test_mcp_returns_actual_counts_and_rejects_escapes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'
            shutil.copytree(ROOT / 'tests/fixtures/minimal_project', root)
            (root / 'evidence.log').write_text('ordinary\nFATAL: 错误\nFAIL\n', encoding='utf-8')
            result = _call_tool('search_artifact', {'path': 'evidence.log', 'queries': ['FATAL', 'FAIL']}, root, None, False)
            data = json.loads(result['content'][0]['text'])
            self.assertTrue(data['scan_complete'])
            self.assertEqual([q['count'] for q in data['queries']], [1, 1])
            self.assertEqual([m['line_number'] for m in data['matches']], [2, 3])
            with self.assertRaises(KitError):
                _call_tool('search_artifact', {'path': '../evidence.log', 'queries': ['FATAL']}, root, None, False)

    def test_cli_repeated_queries_returns_bounded_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'log.txt').write_text('FATAL x\nFATAL y\nPASS\n', encoding='utf-8')
            process = subprocess.run([sys.executable, '-B', str(ROOT / 'bin/claude-kit'), 'artifact', 'search',
                '--project-root', str(root), '--file', 'log.txt', '--query', 'FATAL', '--query', 'PASS', '--max-output-bytes', '5'],
                capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), timeout=20)
            self.assertEqual(process.returncode, 0, process.stderr)
            data = json.loads(process.stdout)
            self.assertEqual([q['count'] for q in data['queries']], [2, 1])
            self.assertLessEqual(data['output_bytes'], 5)
            self.assertTrue(data['output_truncated'])


if __name__ == '__main__':
    unittest.main()
