#!/usr/bin/env python3
"""Bounded SystemVerilog source navigation and diagnostics through Verible LSP.

Parsing/indexing is not preprocessing, elaboration, or simulation sign-off.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
from functools import wraps
from urllib.parse import unquote, urlparse

from mcp.server.fastmcp import FastMCP

MAX_RESPONSE = 12000
MAX_FRAME = 16 * 1024 * 1024
MAX_SOURCE = 8 * 1024 * 1024
SV_SUFFIXES = ('.sv', '.svh', '.svp', '.v', '.vh', '.vp')



def serialized(function):
    @wraps(function)
    def call(self, *args, **kwargs):
        with self.operation_lock:
            return function(self, *args, **kwargs)
    return call


def page(key, items, offset=0, limit=40, expected_snapshot=None, **metadata):
    """Paginate without silently discarding nested symbols or oversized rows."""
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError('offset >= 0 and limit in 1..100 required')
    identity = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
    if expected_snapshot and identity != expected_snapshot:
        raise ValueError('Results changed; restart at offset 0')
    if offset > len(items):
        raise ValueError('Offset exceeds result count')
    result = {key: [], 'total': len(items), 'offset': offset, 'snapshot': identity,
              'next_offset': None, 'truncated': False, **metadata}
    for item in items[offset:offset + limit]:
        result[key].append(item)
        if len(json.dumps(result, ensure_ascii=True).encode()) > MAX_RESPONSE - 256:
            result[key].pop()
            if not result[key]:
                raise ValueError('One result exceeds output budget; narrow the query or inspect its source')
            break
    next_offset = offset + len(result[key])
    result['truncated'] = next_offset < len(items)
    result['next_offset'] = next_offset if result['truncated'] else None
    return json.dumps(result, ensure_ascii=True, separators=(',', ':'))


def flatten_symbols(symbols):
    stack = [(item, '') for item in reversed(symbols)]
    flat = []
    while stack:
        item, parent = stack.pop()
        name = item.get('name', '')
        flat.append({k: item[k] for k in ('name', 'kind', 'range', 'selectionRange', 'location') if k in item} | {'parent': parent})
        stack.extend((child, parent + '.' + name if parent else name)
                     for child in reversed(item.get('children', [])))
    return flat


class VeribleLSPBridge:
    def __init__(self, verible_path=None, root=None, timeout=20):
        self.root = Path(root).resolve() if root else self.find_workspace_root(str(Path.cwd()))
        config_path = self.root / '.claude/soc-lsp.json'
        config = json.loads(config_path.read_text()) if config_path.is_file() else {}
        self.verible_path = verible_path or config.get('verible_path', 'verible-verilog-ls')
        self.bazel_target = config.get('bazel_target')
        self.timeout = timeout
        self.process = None
        self.msg_id = 0
        self.lock = threading.Lock()
        self.operation_lock = threading.RLock()
        self.write_lock = threading.Lock()
        self._workspace_root = None
        self._initialized = False
        self._opened_documents = {}
        self._versions = {}
        self.diagnostics = {}
        self.capabilities = {}
        self.index = None
        self.index_sources = set()
        self.index_artifacts = {}
        self._index_temp = None
        self._responses = queue.Queue()

    def find_workspace_root(self, file_path):
        p = Path(file_path).resolve()
        start = p if p.is_dir() else p.parent
        return next((r for r in (start, *start.parents) if (r / '.git').exists() or (r / '.mcp.json').exists()), start)

    def _source(self, file_path):
        p = Path(file_path).resolve()
        # Production tools start the bridge before opening files. Unit-test
        # protocol seams can exercise didOpen without a live process.
        if self._workspace_root and not self._allowed_source(p):
            raise ValueError('Source is outside the fixed checkout root')
        if p.suffix.lower() not in SV_SUFFIXES or not p.is_file():
            raise ValueError('Expected an existing SystemVerilog/Verilog source file')
        return p

    def _allowed_source(self, path):
        return path.is_relative_to(self.root) or path in self.index_sources

    @serialized
    def start(self, workspace_root=None):
        if workspace_root and Path(workspace_root).resolve() != self.root:
            raise ValueError('Cannot switch checkout in a live MCP server')
        if self.process and self.process.poll() is None and self._initialized:
            return
        self.stop()
        self._workspace_root = self.root
        argv = [self.verible_path]
        if self.index:
            argv += ['--file_list_path=' + self.index['effective_filelist']]
        else:
            # Do not let an ambient filelist silently index external sources.
            # Explicit configure_index validates the project scope first.
            if self._index_temp is None:
                self._index_temp = tempfile.TemporaryDirectory(prefix='soc-lsp-index-')
            empty = Path(self._index_temp.name) / 'verible.filelist'
            empty.write_text('', encoding='utf-8')
            argv += ['--file_list_path=' + str(empty)]
        self.process = subprocess.Popen(argv, cwd=self.root, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._responses = queue.Queue()
        threading.Thread(target=self._read_loop, args=(self.process, self._responses), daemon=True).start()
        try:
            result = self._send_message('initialize', {
                'processId': os.getpid(), 'rootPath': str(self.root), 'rootUri': self.root.as_uri(),
                'capabilities': {'textDocument': {'publishDiagnostics': {'versionSupport': True}}, 'workspace': {}}})
            self.capabilities = result.get('capabilities', {})
            self._send_notification('initialized', {})
            self._initialized = True
        except BaseException:
            self.stop()
            raise

    @staticmethod
    def _frame(stream):
        length = None
        for _ in range(32):
            line = stream.readline(4097)
            if not line or len(line) > 4096:
                raise RuntimeError('LSP closed or malformed header')
            if line in (b'\r\n', b'\n'):
                break
            if line.lower().startswith(b'content-length:'):
                length = int(line.split(b':', 1)[1])
        if length is None or not 0 <= length <= MAX_FRAME:
            raise RuntimeError('Invalid LSP frame length')
        payload = bytearray()
        while len(payload) < length:
            part = stream.read(length - len(payload))
            if not part:
                raise RuntimeError('Truncated LSP frame')
            payload.extend(part)
        return json.loads(payload.decode('utf-8'))

    def _read_loop(self, process, responses):
        try:
            while True:
                responses.put(self._frame(process.stdout))
        except Exception as exc:
            responses.put(exc)

    def _write(self, message):
        payload = json.dumps(message, ensure_ascii=False).encode('utf-8')
        with self.write_lock:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError('LSP server is not running')
            self.process.stdin.write(b'Content-Length: ' + str(len(payload)).encode() + b'\r\n\r\n' + payload)
            self.process.stdin.flush()

    def _send_notification(self, method, params):
        self._write({'jsonrpc': '2.0', 'method': method, 'params': params})

    def _send_message(self, method, params):
        import time
        with self.lock:
            self.msg_id += 1
            mid = self.msg_id
            self._write({'jsonrpc': '2.0', 'id': mid, 'method': method, 'params': params})
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    item = self._responses.get(timeout=max(0.001, deadline - time.monotonic()))
                except queue.Empty:
                    self.stop()
                    raise TimeoutError('Verible request timed out: ' + method)
                if isinstance(item, Exception):
                    self.stop()
                    raise item
                if item.get('method') == 'textDocument/publishDiagnostics':
                    p = item['params']
                    self.diagnostics[p['uri']] = p
                elif 'method' in item and 'id' in item:
                    self._write({'jsonrpc': '2.0', 'id': item['id'], 'error': {'code': -32601, 'message': 'Client method unsupported'}})
                elif item.get('id') == mid:
                    if 'error' in item:
                        raise RuntimeError('Verible LSP error: ' + str(item['error'])[:1000])
                    return item.get('result')
                if time.monotonic() >= deadline:
                    self.stop()
                    raise TimeoutError('Verible request timed out: ' + method)

    @serialized
    def stop(self):
        process = self.process
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=5)
            finally:
                for stream in (process.stdin, process.stdout):
                    if stream:
                        stream.close()
        self.process = None
        self._initialized = False
        self._opened_documents.clear()
        self._versions.clear()
        self.diagnostics.clear()

    def _file_to_uri(self, file_path):
        return Path(file_path).resolve().as_uri()

    def _uri_to_file(self, uri):
        parsed = urlparse(uri)
        if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
            raise ValueError('Unsupported source URI')
        path = unquote(parsed.path)
        if os.name == 'nt' and len(path) > 2 and path[0] == '/' and path[2] == ':':
            path = path[1:]
        return path

    def _ensure_document_open(self, file_path):
        path = self._source(file_path)
        with path.open('rb') as stream:
            data = stream.read(MAX_SOURCE + 1)
        if len(data) > MAX_SOURCE:
            raise ValueError('Source exceeds 8 MiB; use a narrower source unit')
        key = str(path)
        digest = hashlib.sha256(data).hexdigest()
        if self._opened_documents.get(key) == digest:
            return
        uri = path.as_uri()
        if key in self._opened_documents:
            self._send_notification('textDocument/didClose', {'textDocument': {'uri': uri}})
        self.diagnostics.pop(uri, None)
        self._versions[key] = self._versions.get(key, 0) + 1
        self._send_notification('textDocument/didOpen', {'textDocument': {
            'uri': uri, 'languageId': 'verilog', 'version': self._versions[key],
            'text': data.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')}})
        self._opened_documents[key] = digest

    def _normalize_locations(self, locations):
        if isinstance(locations, dict):
            locations = [locations]
        result = []
        for loc in locations or []:
            p = Path(self._uri_to_file(loc.get('uri', loc.get('targetUri')))).resolve()
            if not self._allowed_source(p):
                raise ValueError('LSP returned a location outside the checkout')
            result.append({'file': str(p), 'range': loc.get('range', loc.get('targetRange', {}))})
        return result

    @serialized
    def _at(self, method, file_path, line, column, **extra):
        if line < 0 or column < 0:
            raise ValueError('LSP positions are zero-based nonnegative integers')
        self._ensure_document_open(file_path)
        return self._send_message(method, {'textDocument': {'uri': self._file_to_uri(file_path)},
                                  'position': {'line': line, 'character': column}, **extra})

    def go_to_definition(self, file_path, line, column):
        return self._normalize_locations(self._at('textDocument/definition', file_path, line, column))

    def find_references(self, file_path, line, column, include_declaration=True):
        return self._normalize_locations(self._at('textDocument/references', file_path, line, column,
                                         context={'includeDeclaration': include_declaration}))

    @serialized
    def document_symbol(self, file_path):
        self._ensure_document_open(file_path)
        return self._send_message('textDocument/documentSymbol', {'textDocument': {'uri': self._file_to_uri(file_path)}}) or []

    @serialized
    def get_diagnostics(self, file_path):
        # A request after didOpen acts as a protocol barrier for Verible's
        # synchronous parse notifications. Absence is explicitly not a clean parse.
        self.document_symbol(file_path)
        uri = self._file_to_uri(file_path)
        diagnostic = self.diagnostics.get(uri)
        version = self._versions[str(Path(file_path).resolve())]
        if diagnostic is None or diagnostic.get('version', version) != version:
            return {'state': 'pending', 'items': [], 'version': version}
        return {'state': 'reported', 'items': diagnostic.get('diagnostics', []), 'version': version,
                'versioned': 'version' in diagnostic}

    @serialized
    def configure_index(self, filelist_path):
        manifest = Path(filelist_path).resolve()
        if not manifest.is_relative_to(self.root):
            raise ValueError('Filelist must be an explicitly selected file inside the checkout')
        with manifest.open('rb') as f:
            raw = f.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Filelist exceeds 1 MiB')
        paths = []
        for line in raw.decode('utf-8').splitlines():
            entry = line.strip()
            if not entry or entry.startswith('#'):
                continue
            if entry.startswith(('-', '+')):
                raise ValueError('Expected a plain source list, not simulator flags or nested filelists')
            p = (manifest.parent / entry).resolve()
            if not p.is_relative_to(self.root):
                raise ValueError('Indexed source escapes the checkout: ' + entry[:200])
            self._source(p)
            if p not in paths:
                paths.append(p)
        if not paths or len(paths) > 20000:
            raise ValueError('Expected 1..20000 source files')
        self.index_artifacts = {}
        self.index_sources = set()
        return self._install_index(paths, {'filelist': str(manifest), 'sha256': hashlib.sha256(raw).hexdigest(),
                                          'authority': 'explicit_subset', 'full_tb': False})

    def _install_index(self, paths, metadata):
        self.stop()
        if self._index_temp:
            self._index_temp.cleanup()
        self._index_temp = tempfile.TemporaryDirectory(prefix='soc-lsp-index-')
        effective = Path(self._index_temp.name) / 'verible.filelist'
        effective.write_text('\n'.join(str(p) for p in paths) + '\n', encoding='utf-8')
        self.index = {**metadata, 'sources': len(paths), 'effective_filelist': str(effective)}
        self.start()
        return self.index_status()

    @serialized
    def configure_sys_tb_index(self):
        """Consume project-configured Bazel testbench outputs; never infer authority from a plain filelist."""
        target = self.bazel_target
        import re
        if not isinstance(target, str) or not re.fullmatch(r'//[A-Za-z0-9_./-]+:[A-Za-z0-9_.-]+', target):
            raise ValueError('Set bazel_target to an explicit //package:target in .claude/soc-lsp.json')
        package, name = target[2:].split(':')
        if any(part in ('.', '..') for part in package.split('/')) or name in ('.', '..'):
            raise ValueError('Invalid Bazel target path')
        base = self.root / 'bazel-bin' / package
        artifacts = {}
        def read(name):
            path = base / name
            with path.open('rb') as stream:
                raw = stream.read(MAX_FRAME + 1)
            if len(raw) > MAX_FRAME:
                raise ValueError('Generated artifact exceeds 16 MiB: ' + name)
            artifacts[str(path)] = hashlib.sha256(raw).hexdigest()
            return raw.decode('utf-8')
        inventory = read((name + '_compile_inputs.txt'))
        mapping = read((name + '.runfiles_manifest'))
        read((name + '_compile_args.f'))
        digest = read((name + '_compile_inputs.sha256')).strip()
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid generated compile-input digest')
        runfiles = {}
        for line in mapping.splitlines():
            # Bazel escaped-manifest records need explicit decoding; fail closed.
            if line.startswith(' '):
                raise ValueError('Escaped Bazel runfiles records are not supported')
            key, sep, target = line.partition(' ')
            if not sep or not Path(target).is_absolute():
                raise ValueError('Expected an absolute Bazel runfiles mapping')
            if key in runfiles and runfiles[key] != target:
                raise ValueError('Conflicting runfiles mapping')
            runfiles[key] = target
        paths, seen, ignored = [], set(), {}
        for line in inventory.splitlines():
            kind, sep, name = line.partition('\t')
            if not sep or kind not in ('source', 'filelist', 'runfile'):
                raise ValueError('Invalid generated compile-input inventory record')
            if kind == 'filelist':
                continue
            suffix = Path(name).suffix.lower()
            if suffix not in SV_SUFFIXES:
                ignored[suffix or '(none)'] = ignored.get(suffix or '(none)', 0) + 1
                continue
            # Inventory names are runfiles-root-relative, not manifest-relative.
            target = runfiles.get('__main__/' + name)
            if target is None:
                raise ValueError('Generated source missing from runfiles mapping: ' + name[:200])
            path = Path(target).resolve()
            if not path.is_file():
                raise ValueError('Generated source is unavailable: ' + name[:200])
            if path not in seen:
                paths.append(path)
                seen.add(path)
        if not paths or len(paths) > 20000:
            raise ValueError('Expected 1..20000 generated SV sources')
        self.index_artifacts = artifacts
        self.index_sources = seen
        return self._install_index(paths, {
            'authority': 'bazel_generated_compile_inventory', 'target': target,
            'generation_command': 'bazel build ' + target,
            'filelist': str(base / (name + '_compile_inputs.txt')),
            'sha256': artifacts[str(base / (name + '_compile_inputs.txt'))],
            'compile_inputs_digest': digest, 'excluded_input_extensions': ignored,
            'external_sources': sum(not p.is_relative_to(self.root) for p in paths),
            'build_freshness': 'not_verified_run_bazel_build_to_refresh',
            'full_tb': False, 'coverage': 'all_supported_SV_entries_in_generated_inventory',
        })

    @serialized
    def index_status(self):
        current = False
        if self.index:
            try:
                expected = self.index_artifacts or {self.index['filelist']: self.index['sha256']}
                current = True
                for path, sha in expected.items():
                    with Path(path).open('rb') as stream:
                        raw = stream.read(MAX_FRAME + 1)
                    current = current and len(raw) <= MAX_FRAME and hashlib.sha256(raw).hexdigest() == sha
            except OSError:
                current = False
        return {'root': str(self.root), 'configured': self.index is not None, 'manifest_current': current,
                'index': {k: v for k, v in (self.index or {}).items() if k != 'effective_filelist'},
                'default_filelist_present': (self.root / 'verible.filelist').is_file(),
                'capabilities': self.capabilities,
                'limitation': 'Source parsing only; macros, elaboration and dynamic UVM factory behavior require compiler/runtime evidence.'}


lsp_bridge = None


def get_lsp_bridge(file_path=None):
    global lsp_bridge
    if lsp_bridge is None:
        lsp_bridge = VeribleLSPBridge()
    if file_path and not lsp_bridge._allowed_source(Path(file_path).resolve()):
        raise ValueError('Source is outside the fixed checkout root')
    lsp_bridge.start()
    return lsp_bridge


mcp = FastMCP('verible-lsp')


@mcp.tool()
def index_status() -> str:
    """Check root, selected source manifest and actual server capabilities before project-wide navigation."""
    return json.dumps(get_lsp_bridge().index_status())


@mcp.tool()
def configure_index(filelist_path: str) -> str:
    """Index an explicit partial plain SV list. For SoC use configure_sys_tb_index and Bazel sys_tb outputs; verible.filelist is not authoritative."""
    return json.dumps(get_lsp_bridge().configure_index(filelist_path))


@mcp.tool()
def configure_sys_tb_index() -> str:
    """Index outputs of the bazel_target configured in .claude/soc-lsp.json using its full compile inventory and runfiles map. Read-only; run the build first for freshness. Does not run Bazel or simulation."""
    return json.dumps(get_lsp_bridge().configure_sys_tb_index())


@mcp.tool()
def document_symbols(file_path: str, offset: int = 0, limit: int = 40, name_filter: str = '', expected_snapshot: str = '') -> str:
    """Return a flat module/class/task/function outline with parent names and zero-based ranges; paginate using next_offset and snapshot."""
    symbols = flatten_symbols(get_lsp_bridge(file_path).document_symbol(file_path))
    if name_filter:
        symbols = [s for s in symbols if name_filter.casefold() in s['name'].casefold()]
    return page('symbols', symbols, offset, limit, expected_snapshot)


@mcp.tool()
def go_to_definition(file_path: str, line: int, column: int, offset: int = 0, limit: int = 40, expected_snapshot: str = '') -> str:
    """Resolve a symbol at a zero-based LSP position. Cross-file completeness depends on the selected index; empty does not prove absence."""
    bridge = get_lsp_bridge(file_path)
    return page('locations', bridge.go_to_definition(file_path, line, column), offset, limit, expected_snapshot)


@mcp.tool()
def find_references(file_path: str, line: int, column: int, include_declaration: bool = True, offset: int = 0, limit: int = 40, expected_snapshot: str = '') -> str:
    """Return bounded reference locations at a zero-based position. Request further pages only when needed; index gaps are not proof of no references."""
    bridge = get_lsp_bridge(file_path)
    return page('references', bridge.find_references(file_path, line, column, include_declaration), offset, limit, expected_snapshot)


@mcp.tool()
def get_diagnostics(file_path: str, offset: int = 0, limit: int = 40, expected_snapshot: str = '') -> str:
    """Return current Verible syntax/style diagnostics. pending means unavailable, not zero errors; these are not VCS or DV pass evidence."""
    result = get_lsp_bridge(file_path).get_diagnostics(file_path)
    return page('diagnostics', result.pop('items'), offset, limit, expected_snapshot, **result)


@mcp.tool()
def hover(file_path: str, line: int, column: int) -> str:
    """Return bounded symbol documentation if the installed Verible advertises hover support."""
    bridge = get_lsp_bridge(file_path)
    if not bridge.capabilities.get('hoverProvider'):
        return json.dumps({'supported': False, 'reason': 'Installed server does not advertise hover'})
    result = bridge._at('textDocument/hover', file_path, line, column)
    return page('hover', [result] if result else [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sse', action='store_true')
    args = parser.parse_args()
    try:
        mcp.run(transport='sse' if args.sse else 'stdio')
    finally:
        if lsp_bridge:
            lsp_bridge.stop()
            if lsp_bridge._index_temp:
                lsp_bridge._index_temp.cleanup()


if __name__ == '__main__':
    main()
