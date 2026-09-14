"""Optional Make MCP filelist arguments must retain their documented meaning."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from claude_kit.adaptations import export_adapted


class MakeFilelistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        exported = Path(cls.temp.name) / 'adapted'
        export_adapted(exported)
        cls.base = exported / 'source/.agents/skills/soc-build'
        # Unit-test only the wrapper/CLI boundary without importing FastMCP,
        # tool backends or starting an EDA process. Runtime MCP is tested on ETX.
        tree = ast.parse((cls.base / 'mcp_server.py').read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'soc_flist')
        function.decorator_list = []
        cls.code = compile(ast.Module(body=[function], type_ignores=[]), 'soc_flist-unit', 'exec')

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.scan = self.root / 'input'
        (self.scan / 'nested').mkdir(parents=True)
        (self.scan / 'top.sv').write_text('module top; endmodule\n')
        (self.scan / 'nested/child.v').write_text('module child; endmodule\n')
        (self.root / 'filelist.f').write_text('preserve existing filelist\n')
        namespace = {'_python': self.run_helper}
        exec(self.code, namespace)
        self.tool = namespace['soc_flist']

    def run_helper(self, script, *args):
        result = subprocess.run([sys.executable, str(self.base / 'scripts' / script), *args],
            cwd=self.root, env={**os.environ, 'PYTHONUTF8': '1'}, capture_output=True,
            text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def entries(self, content):
        return {line for line in content.splitlines() if line and not line.startswith('#')}

    def test_explicit_recursion_selection_is_obeyed(self):
        for recursive in (False, True):
            with self.subTest(recursive=recursive):
                output = self.root / f'{recursive}.f'
                self.tool(str(self.scan), str(output), recursive)
                expected = {str(self.scan / 'top.sv')}
                if recursive:
                    expected.add(str(self.scan / 'nested/child.v'))
                self.assertEqual(self.entries(output.read_text()), expected)

    def test_omitted_output_returns_text_and_preserves_cwd_filelist(self):
        response = self.tool(str(self.scan))
        self.assertEqual((self.root / 'filelist.f').read_text(), 'preserve existing filelist\n')
        self.assertEqual(self.entries(response), {str(self.scan / 'top.sv')})
        self.assertFalse((self.root / '-').exists())

    def test_cli_default_file_output_remains_compatible(self):
        self.run_helper('soc_gen_flist.py', str(self.scan))
        self.assertEqual(self.entries((self.root / 'filelist.f').read_text()),
                         {str(self.scan / 'top.sv'), str(self.scan / 'nested/child.v')})


if __name__ == '__main__':
    unittest.main()
