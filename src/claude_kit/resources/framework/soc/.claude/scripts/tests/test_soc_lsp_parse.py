"""License-free protocol, scope, pagination and freshness regressions."""
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, MagicMock


def load():
    source = Path(os.environ.get('SOC_LSP_SOURCE', str(Path(__file__).resolve().parents[2] / 'skills/soc-lsp/mcp_server.py')))
    module = types.ModuleType('mcp.server.fastmcp')
    class FakeMCP:
        def __init__(self, *args): pass
        def tool(self): return lambda function: function
    module.FastMCP = FakeMCP
    spec = importlib.util.spec_from_file_location('parse_bridge', source)
    loaded = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'mcp.server.fastmcp': module}):
        spec.loader.exec_module(loaded)
    return loaded


class ParseTests(unittest.TestCase):
    def make_bazel_outputs(self, external):
        base = self.root / 'bazel-bin/hw/dv/project_benches/sys/tb'
        base.mkdir(parents=True)
        (base / 'sys_tb_compile_inputs.txt').write_text('source\ttop.sv\nsource\texternal/pkg/defs.vp\nrunfile\tlib.so\n')
        (base / 'sys_tb.runfiles_manifest').write_text('__main__/top.sv ' + str(self.source) + '\n__main__/external/pkg/defs.vp ' + str(external) + '\n')
        (base / 'sys_tb_compile_args.f').write_text('-sverilog\n')
        (base / 'sys_tb_compile_inputs.sha256').write_text('0' * 64 + '\n')
        return base

    def test_bazel_inventory_external_scope_and_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            external = Path(tmp) / 'defs.vp'
            external.write_text('module child; endmodule\n')
            base = self.make_bazel_outputs(external)
            with patch.object(self.bridge, 'start'):
                result = self.bridge.configure_sys_tb_index()
            self.addCleanup(self.bridge._index_temp.cleanup)
            self.assertEqual(result['index']['sources'], 2)
            self.assertEqual(result['index']['external_sources'], 1)
            self.assertTrue(result['manifest_current'])
            self.assertTrue(self.bridge._allowed_source(external.resolve()))
            self.assertFalse(self.bridge._allowed_source(Path(tmp) / 'unlisted.sv'))
            (base / 'sys_tb_compile_args.f').write_text('-sverilog\n+define+CHANGED\n')
            self.assertFalse(self.bridge.index_status()['manifest_current'])

    def test_bazel_missing_source_is_not_silently_dropped(self):
        self.make_bazel_outputs(self.root / 'missing.vp')
        with patch.object(self.bridge, 'start'), self.assertRaisesRegex(ValueError, 'unavailable'):
            self.bridge.configure_sys_tb_index()
        self.assertIsNone(self.bridge.index)

    def test_bazel_does_not_use_ambient_verible_list(self):
        (self.root / 'verible.filelist').write_text('top.sv\n')
        with patch.object(self.bridge, 'start'), self.assertRaises(FileNotFoundError):
            self.bridge.configure_sys_tb_index()

    def test_other_project_target_controls_all_artifact_names(self):
        external = self.root / 'defs.vp'
        external.write_text('module child; endmodule')
        old = self.make_bazel_outputs(external)
        new = self.root / 'bazel-bin/benches/alternate'
        new.mkdir(parents=True)
        for path in old.iterdir():
            path.rename(new / path.name.replace('sys_tb', 'selected', 1))
        self.bridge.bazel_target = '//benches/alternate:selected'
        with patch.object(self.bridge, 'start'):
            result = self.bridge.configure_sys_tb_index()
        self.addCleanup(self.bridge._index_temp.cleanup)
        self.assertEqual(result['index']['target'], '//benches/alternate:selected')
        self.assertTrue(Path(result['index']['filelist']).as_posix().endswith('/benches/alternate/selected_compile_inputs.txt'))

    def test_missing_or_escaping_target_is_not_inferred(self):
        for target in (None, '///etc:target', '//../escape:target'):
            with self.subTest(target=target):
                self.bridge.bazel_target = target
                with self.assertRaises(ValueError):
                    self.bridge.configure_sys_tb_index()

    def setUp(self):
        self.mod = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'top.sv'
        self.source.write_text('module top; endmodule\n')
        (self.root / '.claude').mkdir(exist_ok=True)
        (self.root / '.claude/soc-lsp.json').write_text(json.dumps({'bazel_target': '//hw/dv/project_benches/sys/tb:sys_tb'}))
        self.bridge = self.mod.VeribleLSPBridge(root=self.root, timeout=0.02)

    def test_nested_symbols_are_flat_and_losslessly_paginated(self):
        tree = [{'name': 'top', 'kind': 2, 'children': [{'name': 'f%d' % i, 'kind': 12} for i in range(600)]}]
        flat = self.mod.flatten_symbols(tree)
        observed = []
        offset, snapshot = 0, ''
        while True:
            text = self.mod.page('symbols', flat, offset, 40, snapshot)
            self.assertLessEqual(len(text.encode()), self.mod.MAX_RESPONSE)
            result = json.loads(text)
            observed.extend(result['symbols'])
            snapshot = result['snapshot']
            offset = result['next_offset']
            if offset is None: break
        self.assertEqual(len(observed), 601)
        self.assertEqual(observed[-1]['parent'], 'top')

    def test_changed_pagination_snapshot_rejected(self):
        p = json.loads(self.mod.page('items', [1, 2], 0, 1))
        with self.assertRaisesRegex(ValueError, 'Results changed'):
            self.mod.page('items', [1, 3], 1, 1, p['snapshot'])

    def test_oversized_row_is_not_silently_lost(self):
        with self.assertRaisesRegex(ValueError, 'exceeds output budget'):
            self.mod.page('items', [{'name': 'a' * 20000}])

    def test_utf8_frame_and_extra_headers(self):
        payload = json.dumps({'message': '妯″潡'}, ensure_ascii=False).encode()
        data = b'Content-Length: ' + str(len(payload)).encode() + b'\r\nContent-Type: application/vscode-jsonrpc\r\n\r\n' + payload
        self.assertEqual(self.bridge._frame(io.BytesIO(data))['message'], '妯″潡')
        with self.assertRaisesRegex(RuntimeError, 'Truncated'):
            self.bridge._frame(io.BytesIO(data[:-1]))

    def test_write_uses_utf8_byte_length(self):
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdin = io.BytesIO()
        self.bridge.process = proc
        self.bridge._write({'message': '妯″潡'})
        header, payload = proc.stdin.getvalue().split(b'\r\n\r\n')
        self.assertEqual(int(header.split(b':')[1]), len(payload))

    def test_diagnostics_not_discarded_while_waiting_for_reply(self):
        self.bridge._write = lambda msg: None
        uri = self.source.as_uri()
        self.bridge._responses.put({'method': 'textDocument/publishDiagnostics', 'params': {'uri': uri, 'version': 1, 'diagnostics': [{'message': 'syntax error'}]}})
        self.bridge._responses.put({'id': 1, 'result': []})
        self.assertEqual(self.bridge._send_message('textDocument/documentSymbol', {}), [])
        self.assertEqual(self.bridge.diagnostics[uri]['diagnostics'][0]['message'], 'syntax error')

    def test_missing_and_stale_diagnostics_are_pending(self):
        self.bridge.document_symbol = lambda p, **kwargs: []
        self.bridge._versions[str(self.source.resolve())] = 2
        self.assertEqual(self.bridge.get_diagnostics(self.source)['state'], 'pending')
        self.bridge.diagnostics[self.source.as_uri()] = {'version': 1, 'diagnostics': []}
        self.assertEqual(self.bridge.get_diagnostics(self.source)['state'], 'pending')
        self.bridge.diagnostics[self.source.as_uri()] = {'version': 2, 'diagnostics': []}
        self.assertEqual(self.bridge.get_diagnostics(self.source)['state'], 'reported')

    def test_changed_source_clears_previous_diagnostics(self):
        calls = []
        self.bridge._send_notification = lambda method, params: calls.append(method)
        self.bridge._ensure_document_open(self.source)
        self.bridge.diagnostics[self.source.as_uri()] = {'diagnostics': []}
        self.source.write_text('module changed; endmodule\n')
        self.bridge._ensure_document_open(self.source)
        self.assertNotIn(self.source.as_uri(), self.bridge.diagnostics)
        self.assertEqual(calls, ['textDocument/didOpen', 'textDocument/didClose', 'textDocument/didOpen'])

    def test_timeout_is_bounded_and_stops_owned_process(self):
        self.bridge._write = lambda msg: None
        self.bridge.stop = MagicMock()
        with self.assertRaises(TimeoutError): self.bridge._send_message('hung', {})
        self.bridge.stop.assert_called_once()

    def test_index_accepts_explicit_paths_and_records_drift(self):
        filelist = self.root / 'selected.f'
        filelist.write_text('top.sv\n')
        self.bridge.start = lambda: None
        result = self.bridge.configure_index(filelist)
        self.addCleanup(self.bridge._index_temp.cleanup)
        self.assertTrue(result['manifest_current'])
        self.assertEqual(result['index']['sources'], 1)
        self.assertEqual(filelist.read_text(), 'top.sv\n')
        filelist.write_text('# changed\ntop.sv\n')
        self.assertFalse(self.bridge.index_status()['manifest_current'])

    def test_index_rejects_flags_and_outside_paths(self):
        filelist = self.root / 'selected.f'
        for value in ['+incdir+foo', '../outside.sv', '-f nested.f']:
            filelist.write_text(value + '\n')
            with self.assertRaises(ValueError): self.bridge.configure_index(filelist)

    def test_svp_vp_open_and_index(self):
        self.bridge._workspace_root = self.root
        opened = []
        self.bridge._send_notification = lambda method, params: opened.append((method, params))
        names = ['block.svp', 'legacy.vp', 'upper.SVP', 'upper.VP']
        for name in names:
            source = self.root / name
            source.write_text('module block; endmodule\n')
            self.bridge._ensure_document_open(source)
        self.assertEqual(len(opened), 4)
        self.assertTrue(all(p['textDocument']['languageId'] == 'verilog' for _, p in opened))
        filelist = self.root / 'extensions.f'
        filelist.write_text('\n'.join(names) + '\n')
        self.bridge.start = lambda: None
        result = self.bridge.configure_index(filelist)
        self.addCleanup(self.bridge._index_temp.cleanup)
        self.assertEqual(result['index']['sources'], 4)

    def test_unrelated_extension_remains_rejected(self):
        source = self.root / 'notes.txt'
        source.write_text('module block; endmodule\n')
        with self.assertRaises(ValueError): self.bridge._source(source)

    def test_location_and_source_cannot_escape_checkout(self):
        with tempfile.TemporaryDirectory() as outside:
            p = Path(outside) / 'foreign.sv'
            p.write_text('module foreign; endmodule')
            self.bridge._workspace_root = self.root
            with self.assertRaises(ValueError): self.bridge._source(p)
            with self.assertRaises(ValueError): self.bridge._normalize_locations([{'uri': p.as_uri()}])

    def test_hover_capability_is_honored(self):
        with patch.object(self.mod, 'get_lsp_bridge', return_value=self.bridge):
            self.assertFalse(json.loads(self.mod.hover(str(self.source), 0, 0))['supported'])

    def test_references_add_and_deduplicate_declarations(self):
        definition = {'file': str(self.source), 'range': {'start': {'line': 0, 'character': 7}}}
        usage = {'file': str(self.source), 'range': {'start': {'line': 2, 'character': 3}}}
        self.bridge._at = lambda *args, **kwargs: [
            {'uri': self.source.as_uri(), 'range': usage['range']}]
        self.bridge.go_to_definition = lambda *args: [definition]
        self.assertEqual(self.bridge.find_references(self.source, 0, 7), [usage, definition])
        self.assertEqual(self.bridge.find_references(self.source, 0, 7, False), [usage])
        self.bridge._at = lambda *args, **kwargs: [
            {'uri': self.source.as_uri(), 'range': definition['range']},
            {'uri': self.source.as_uri(), 'range': definition['range']}]
        self.assertEqual(self.bridge.find_references(self.source, 0, 7), [definition])
        self.assertEqual(self.bridge.find_references(self.source, 0, 7, False), [])

    def test_definition_links_use_identifier_selection_range(self):
        selected = {'start': {'line': 1, 'character': 7}, 'end': {'line': 1, 'character': 10}}
        location = {'targetUri': self.source.as_uri(), 'targetRange': {}, 'targetSelectionRange': selected}
        self.assertEqual(self.bridge._normalize_locations([location])[0]['range'], selected)

    def test_symbol_cache_avoids_roundtrips_but_detects_same_mtime_edits(self):
        self.bridge._send_notification = lambda *args: None
        self.bridge._send_message = MagicMock(side_effect=[[{'name': 'old'}], [{'name': 'new'}], [{'name': 'new'}]])
        self.source.write_text('module old; endmodule\n')
        self.assertEqual(self.bridge.document_symbol(self.source)[0]['name'], 'old')
        for _ in range(10):
            self.assertEqual(self.bridge.document_symbol(self.source)[0]['name'], 'old')
        self.assertEqual(self.bridge._send_message.call_count, 1)
        saved = self.source.stat()
        self.source.write_text('module new; endmodule\n')
        os.utime(self.source, ns=(saved.st_atime_ns, saved.st_mtime_ns))
        self.assertEqual(self.bridge.document_symbol(self.source)[0]['name'], 'new')
        self.assertEqual(self.bridge._send_message.call_count, 2)
        self.bridge.stop()
        self.assertEqual(self.bridge.document_symbol(self.source)[0]['name'], 'new')
        self.assertEqual(self.bridge._send_message.call_count, 3)

    def test_cached_symbols_do_not_replace_diagnostic_protocol_barrier(self):
        self.bridge._send_notification = lambda *args: None
        self.bridge._send_message = MagicMock(return_value=[])
        self.bridge.document_symbol(self.source)
        self.assertEqual(self.bridge.get_diagnostics(self.source)['state'], 'pending')
        self.assertEqual(self.bridge._send_message.call_count, 2)

    def test_symbol_cache_is_bounded_and_evicted_documents_are_requested_again(self):
        self.bridge._send_notification = lambda *args: None
        self.bridge._send_message = MagicMock(return_value=[])
        with patch.object(self.mod, 'MAX_SYMBOL_CACHE_DOCUMENTS', 2), patch.object(self.mod, 'MAX_SYMBOL_CACHE_BYTES', 4):
            sources = []
            for n in range(3):
                source = self.root / ('m%d.sv' % n)
                source.write_text('module m; endmodule\n')
                sources.append(source)
                self.bridge.document_symbol(source)
            self.bridge.document_symbol(sources[0])
            self.assertEqual(self.bridge._send_message.call_count, 4)
            self.assertLessEqual(self.bridge._symbol_cache_bytes, 4)
            self.assertLessEqual(len(self.bridge._symbol_cache), 2)

    def test_configure_tool_does_not_launch_an_unused_empty_index_server(self):
        bridge = MagicMock()
        bridge.configure_sys_tb_index.return_value = {}
        with patch.object(self.mod, 'get_lsp_bridge', return_value=bridge) as get:
            self.mod.configure_sys_tb_index()
        get.assert_called_once_with(start_server=False)


if __name__ == '__main__':
    unittest.main()
