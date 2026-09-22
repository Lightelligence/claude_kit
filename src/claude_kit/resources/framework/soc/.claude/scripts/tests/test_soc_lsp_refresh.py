"""License-free regression for document refresh in the Verible MCP bridge."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def load_bridge():
    source = Path(os.environ.get('SOC_LSP_SOURCE',
        str(Path(__file__).resolve().parents[2] / 'skills/soc-lsp/mcp_server.py')))
    module = types.ModuleType('mcp.server.fastmcp')
    class FakeMCP:
        def __init__(self, *args):
            pass
        def tool(self):
            return lambda function: function
    module.FastMCP = FakeMCP
    spec = importlib.util.spec_from_file_location('refresh_bridge', source)
    loaded = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'mcp.server.fastmcp': module}):
        spec.loader.exec_module(loaded)
    return loaded.VeribleLSPBridge


class RefreshTest(unittest.TestCase):
    def test_edit_is_visible_without_restart(self):
        bridge = load_bridge()()
        buffers = {}
        notifications = []
        def notify(method, params):
            document = params['textDocument']
            notifications.append(method)
            if method == 'textDocument/didClose':
                buffers.pop(document['uri'])
            elif method == 'textDocument/didOpen':
                buffers[document['uri']] = document['text']
            else:
                self.fail('Unexpected protocol method: ' + method)
        bridge._send_notification = notify
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'refresh.sv'
            file.write_text('module old_name; endmodule\n')
            bridge._ensure_document_open(str(file))
            bridge._ensure_document_open(str(file))
            self.assertEqual(len(notifications), 1, 'Unchanged document reopened')
            stat = file.stat()
            file.write_text('module new_name; endmodule\n')
            os.utime(file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            bridge._ensure_document_open(str(file))
            self.assertEqual(list(buffers.values()), ['module new_name; endmodule\n'])
            # Restart invalidates the local open-document cache.
            bridge.stop()
            bridge._ensure_document_open(str(file))
            self.assertEqual(notifications[-1], 'textDocument/didOpen')


if __name__ == '__main__':
    unittest.main()
