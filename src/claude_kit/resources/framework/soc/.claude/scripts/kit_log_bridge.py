"""Project-owned read-only log tools alongside the pinned kit MCP tools.

The kit's framing, profile validation and original tool dispatch remain unchanged.
Private integration points are covered by the stdio contract test on kit upgrades.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from dv_log_evidence import summarize, read_range, fit_output, MAX_SCAN_BYTES

DEFAULT_READ_BYTES = 12000


def context_arguments(arguments):
    """Do not implicitly load every profile-default role and protocol pack."""
    from claude_kit.core import KitError
    task = arguments.get('task')
    if not isinstance(task, str) or not task.strip():
        raise KitError('resolve_context requires task; use get_project_profile for project facts')
    selected = dict(arguments)
    for key in ('roles', 'packs', 'skills'):
        value = selected.setdefault(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise KitError(key + ' must be an explicit array; use [] when not needed')
    return selected


def read_bounded_artifact(name, arguments, root, profile_path):
    """Preserve kit path boundaries without reading an entire multi-GB log."""
    from claude_kit.core import KitError, load_profile, _regression_config, _project_path, MAX_ARTIFACT_BYTES
    path = arguments.get('path')
    limit = arguments.get('max_bytes', DEFAULT_READ_BYTES)
    if not isinstance(path, str) or not path.strip():
        raise KitError('artifact path must be a non-empty string')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= MAX_ARTIFACT_BYTES:
        raise KitError('max_bytes must be an integer in 0..' + str(MAX_ARTIFACT_BYTES))
    _, profile = load_profile(root, profile_path)
    regression = name == 'read_regression_artifact'
    base = _regression_config(profile)['root'] if regression else root.resolve()
    if regression:
        candidate = Path(path)
        resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
        if not resolved.is_relative_to(base):
            raise KitError('regression artifact path leaves the configured root')
    else:
        resolved = _project_path(base, path, 'artifact path')
    if not resolved.is_file():
        raise KitError('Artifact does not exist: ' + path)
    with resolved.open('rb') as stream:
        before = os.fstat(stream.fileno())
        data = stream.read(limit)
        after = os.fstat(stream.fileno())
    current = resolved.stat()
    signature = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    value = {'path': str(resolved) if regression else resolved.relative_to(base).as_posix(),
             'bytes': after.st_size, 'truncated': before.st_size > limit or after.st_size > len(data),
             'text': data.decode('utf-8', errors='replace'), 'bytes_read': len(data),
             'stable': signature(before) == signature(after) == signature(current)}
    if regression:
        value.update(relative_path=resolved.relative_to(base).as_posix(), regression_root=str(base))
    return {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False, separators=(',', ':'))}]}


def definitions():
    common = {'path': {'type': 'string'},
        'max_scan_bytes': {'type': 'integer', 'minimum': 1, 'maximum': MAX_SCAN_BYTES},
        'max_output_chars': {'type': 'integer', 'minimum': 4000, 'maximum': 32000}}
    return [
        {'name': 'summarize_regression_log',
         'description': 'Summarize one explicitly selected log: diagnostic counts, first error, context, terminal evidence, and completeness. Never selects a latest run or proves verification signoff.',
         'inputSchema': {'type': 'object', 'additionalProperties': False, 'required': ['path'],
            'properties': {**common, 'max_groups': {'type': 'integer', 'minimum': 1, 'maximum': 20},
                           'context_lines': {'type': 'integer', 'minimum': 0, 'maximum': 5}}},
         'annotations': {'readOnlyHint': True, 'destructiveHint': False}},
        {'name': 'read_regression_log_range',
         'description': 'Expand original log lines (one-based) using the summary fingerprint to reject stale evidence. Reports limits explicitly.',
         'inputSchema': {'type': 'object', 'additionalProperties': False,
            'required': ['path', 'start_line'], 'properties': {**common,
                'start_line': {'type': 'integer', 'minimum': 1},
                'line_count': {'type': 'integer', 'minimum': 1, 'maximum': 200},
                'start_column': {'type': 'integer', 'minimum': 0, 'maximum': 65536},
                'expected_fingerprint': {'type': 'string'}}},
         'annotations': {'readOnlyHint': True, 'destructiveHint': False}},
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--profile', default='.claude/project.toml')
    parser.add_argument('--tool-profile', choices=['compact', 'full'], default='compact')
    args = parser.parse_args()
    root = Path(args.project_root).resolve(strict=True)
    sys.path.insert(0, str(root / 'third_party/claude_kit/src'))
    from claude_kit import mcp_server as kit
    from claude_kit.core import KitError, load_profile, _regression_config
    tools = {item['name']: item for item in definitions()}
    handlers = {'summarize_regression_log': summarize, 'read_regression_log_range': read_range}
    while True:
        request, framing = kit._read_message()
        if request is None:
            return
        request_id, method = request.get('id'), request.get('method')
        try:
            if method == 'initialize':
                result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'claude-kit', 'version': kit.__version__}}
            elif method == 'notifications/initialized':
                continue
            elif method == 'tools/list':
                existing = kit._tool_definitions(False, args.tool_profile)
                for tool in existing:
                    if tool['name'] in ('read_artifact', 'read_regression_artifact'):
                        tool['inputSchema']['properties']['max_bytes']['default'] = DEFAULT_READ_BYTES
                        tool['description'] += ' Defaults to 12000 bytes; prefer summaries and line ranges for logs.'
                    if tool['name'] == 'resolve_context':
                        tool['inputSchema']['required'] = ['task']
                        tool['description'] += ' Pass selected roles/packs/skills; omitted arrays mean none, not profile defaults.'
                        for key in ('roles', 'packs', 'skills'):
                            tool['inputSchema']['properties'][key]['default'] = []
                if set(tools) & {item['name'] for item in existing}:
                    raise KitError('Kit now defines a project log tool; reconcile the project adapter')
                result = {'tools': existing + list(tools.values())}
            elif method == 'tools/call':
                params = request.get('params') or {}
                if not isinstance(params, dict):
                    raise KitError('tools/call params must be an object')
                name, arguments = str(params.get('name', '')), params.get('arguments', {})
                if not isinstance(arguments, dict):
                    raise KitError('tool arguments must be an object')
                if name in tools:
                    schema = tools[name]['inputSchema']
                    if set(arguments) - set(schema['properties']) or set(schema['required']) - set(arguments):
                        raise KitError('Missing or unknown log-tool arguments')
                    _, profile = load_profile(root, args.profile)
                    config = _regression_config(profile)
                    regression_root = config['root']
                    value = handlers[name](regression_root, **arguments)
                    if name == 'summarize_regression_log':
                        relative = Path(value['path']).relative_to(regression_root)
                        value['run_lock_present'] = len(relative.parts) > 1 and any(
                            (regression_root / (relative.parts[0] + config[key])).is_file()
                            for key in ('compile_lock_suffix', 'simulation_lock_suffix'))
                        if value['run_lock_present']:
                            value['status'] = 'unknown'
                        value = fit_output(value, arguments.get('max_output_chars', 12000))
                    result = {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False)}]}
                else:
                    if name in ('read_artifact', 'read_regression_artifact'):
                        result = read_bounded_artifact(name, arguments, root, args.profile)
                    else:
                        if name == 'resolve_context':
                            arguments = context_arguments(arguments)
                        result = kit._call_tool(str(name), arguments, root, args.profile, False)
                # Preserve all fields while avoiding pretty-printed JSON in model context.
                for block in result.get('content', []):
                    if block.get('type') == 'text':
                        try:
                            block['text'] = json.dumps(json.loads(block['text']), ensure_ascii=False, separators=(',', ':'))
                        except (ValueError, TypeError):
                            pass
            else:
                raise KitError(f'Unsupported method: {method}')
            if request_id is not None:
                kit._write_message({'jsonrpc': '2.0', 'id': request_id, 'result': result}, framing)
        except (KitError, OSError, ValueError) as exc:
            if request_id is not None:
                kit._write_message({'jsonrpc': '2.0', 'id': request_id,
                    'error': {'code': -32000, 'message': str(exc)}}, framing)


if __name__ == '__main__':
    main()
