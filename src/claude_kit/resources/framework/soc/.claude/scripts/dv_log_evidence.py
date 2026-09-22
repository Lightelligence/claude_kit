"""Bounded, read-only evidence from one explicitly selected regression log."""
from collections import Counter, deque
import hashlib
import json
import os
from pathlib import Path
import re

MAX_LINE_BYTES = 65536
DEFAULT_SCAN_BYTES = 64 * 1024 * 1024
MAX_SCAN_BYTES = 256 * 1024 * 1024
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
UVM_COUNT = re.compile(r'^\s*(UVM_ERROR|UVM_FATAL|UVM_WARNING)\s*:\s*(\d+)\s*$')
ERROR = re.compile(r'^(?:\s*(?:UVM_ERROR\b|Error-\[|%Error\b|ERROR\b\s*[:\[]))|'
                   r'\b(?:xmvlog|xmelab|xrun|ncvlog|ncelab):\s*\*E,|:\s*error:', re.I)
FATAL = re.compile(r'^\s*(?:UVM_FATAL\b|Fatal-\[|%Fatal\b|FATAL\b\s*[:\[])|'
                   r'\b(?:xmvlog|xmelab|xrun|ncvlog|ncelab):\s*\*F,', re.I)
WARNING = re.compile(r'^\s*(?:UVM_WARNING\b|Warning-\[|WARNING\s*:)|:\s*warning:', re.I)
FAILURE = re.compile(r'\b(?:segmentation fault|assertion\b.*\bfailed|'
    r'license\b.*\b(?:failed|denied|unavailable)|failed to (?:check\s*out|obtain)\b.*license|'
    r'TERM_(?:RUNLIMIT|MEMLIMIT|OWNER)|undefined reference to|'
    r'(?:exit|exited)(?: with)? (?:status|code)\s*[:=]?\s*[1-9]\d*)\b|^Killed\s*$', re.I)
OUTCOME = re.compile(r'^\s*(?:(?:UVM\s+)?TEST|SIMULATION|REGRESSION)'
    r'(?:\s+(?:RESULT|STATUS))?\s*[:=]?\s+(PASSED|PASS|FAILED|FAIL)\b', re.I)


def integer(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError(f'{name} must be an integer in [{lower}, {upper}]')
    return value


def resolve_log(root, path):
    if not isinstance(path, str) or not path.strip():
        raise ValueError('path must name one selected log')
    root = Path(root).resolve(strict=True)
    candidate = Path(path)
    if '..' in candidate.parts:
        raise ValueError('parent traversal is not allowed')
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError('log must be a regular file inside the configured regression root')
    return resolved


def fingerprint(stat):
    fields = [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    return hashlib.sha256(json.dumps(fields).encode()).hexdigest()


def file_identity(stat):
    # Windows path-stat and descriptor-stat may expose different ctime semantics.
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def row(number, text):
    return {'line': number, 'text': text[:320], 'text_truncated': len(text) > 320}


class Scan:
    def __init__(self, path, limit):
        self.path, self.limit = path, limit
        self.bytes_read = self.lines = self.decode_replacements = 0
        self.reason = None
        self.before = path.stat()
        self.after = self.before
        self.digest = hashlib.sha256()
        self.complete = False
        self.stable = False
        self.stop_line = None

    def rows(self):
        with self.path.open('rb') as handle:
            opened = os.fstat(handle.fileno())
            if file_identity(opened) != file_identity(self.before):
                raise ValueError('log changed before reading; retry discovery/summary')
            while self.bytes_read < self.limit:
                raw = handle.readline(min(MAX_LINE_BYTES + 1, self.limit - self.bytes_read))
                if not raw:
                    self.complete = True
                    break
                self.bytes_read += len(raw)
                self.digest.update(raw)
                if len(raw) > MAX_LINE_BYTES:
                    self.reason = 'oversized_line'
                    break
                if not raw.endswith(b'\n') and self.bytes_read < opened.st_size:
                    self.reason = 'byte_limit'
                    break
                text = raw.decode('utf-8', errors='replace').rstrip('\r\n')
                self.decode_replacements += text.count('\ufffd')
                self.lines += 1
                yield self.lines, text
                if self.stop_line is not None and self.lines >= self.stop_line:
                    self.reason = 'range_end'
                    break
            self.complete = self.reason in (None, 'range_end') and handle.tell() == opened.st_size
            if self.complete:
                self.reason = None
            if not self.complete and self.reason is None:
                self.reason = 'byte_limit'
            self.after = self.path.stat()
            self.stable = (fingerprint(self.before) == fingerprint(self.after)
                           and fingerprint(opened) == fingerprint(os.fstat(handle.fileno()))
                           and file_identity(self.after) == file_identity(os.fstat(handle.fileno())))

    def metadata(self):
        return {'path': str(self.path), 'fingerprint': fingerprint(self.before),
            'file_bytes': self.before.st_size, 'scanned_bytes': self.bytes_read,
            'scanned_lines': self.lines, 'scan_complete': self.complete,
            'stop_reason': self.reason, 'stable': self.stable,
            'decode_replacements': self.decode_replacements,
            'sha256': self.digest.hexdigest() if self.complete and self.stable else None}


def category(text):
    lowered = text.lower()
    for name in ('license', 'assertion', 'timeout'):
        if name in lowered:
            return name
    if 'uvm_' in lowered:
        return 'uvm'
    if any(term in lowered for term in ('error-[', 'xmvlog:', 'xmelab:', 'xrun:', 'error:')):
        return 'compiler'
    return 'process_or_generic'


def fit_output(result, budget):
    result['output_truncated'] = result.get('output_truncated', False)
    while len(json.dumps(result, ensure_ascii=False)) > budget:
        result['output_truncated'] = True
        if result.get('diagnostics'):
            removed = result['diagnostics'].pop()
            result['omitted_diagnostic_events'] += removed['count']
        elif result.get('tail'):
            result['tail'].pop(0)
        else:
            break
    return result


def summarize(root, path, max_groups=8, context_lines=2,
              max_scan_bytes=DEFAULT_SCAN_BYTES, max_output_chars=12000):
    integer(max_groups, 'max_groups', 1, 20)
    integer(context_lines, 'context_lines', 0, 5)
    integer(max_scan_bytes, 'max_scan_bytes', 1, MAX_SCAN_BYTES)
    integer(max_output_chars, 'max_output_chars', 4000, 32000)
    scan = Scan(resolve_log(root, path), max_scan_bytes)
    before, tail = deque(maxlen=context_lines), deque(maxlen=8)
    groups, counts, reported_counts = {}, Counter(), {}
    omitted = 0
    first_error = None
    outcome = None
    terminal_reports = {}
    reported_failure = False
    phase = 'unknown'
    for number, text in scan.rows():
        text = ANSI.sub('', text)
        current = row(number, text)
        tail.append(current)
        for group in groups.values():
            if group['first_line'] < number <= group['first_line'] + context_lines:
                group['excerpt'].append(current)
        if re.search(r'Parsing design file|Compiler version|Starting compilation', text, re.I):
            phase = 'compile'
        if re.search(r'^\s*UVM_(?:INFO|WARNING|ERROR|FATAL)\b', text):
            phase = 'simulation'
        count_match = UVM_COUNT.match(text)
        terminal = OUTCOME.match(text)
        if terminal:
            outcome = {**current, 'value': 'passed' if terminal[1].upper().startswith('PASS') else 'failed'}
            terminal_reports.setdefault(outcome['value'], current)
            if outcome['value'] == 'failed' and first_error is None:
                first_error = current
        severity = None
        if count_match:
            reported_counts[count_match[1]] = {'count': int(count_match[2]), 'line': number}
            if count_match[1] != 'UVM_WARNING' and int(count_match[2]) > 0:
                reported_failure = True
                if first_error is None:
                    first_error = current
        elif FATAL.search(text):
            severity = 'fatal'
        elif ERROR.search(text) or FAILURE.search(text):
            severity = 'error'
        elif WARNING.search(text):
            counts['warning'] += 1
        if severity:
            counts[severity] += 1
            if first_error is None:
                first_error = current
            # Exact normalized headers only: addresses, seeds, and values are not erased.
            key = severity + ':' + text.strip()
            if key in groups:
                groups[key]['count'] += 1
                groups[key]['last_line'] = number
            elif len(groups) < max_groups:
                groups[key] = {'severity': severity, 'category': category(text),
                    'count': 1, 'first_line': number, 'last_line': number,
                    'excerpt': list(before) + [current]}
            else:
                omitted += 1
        before.append(current)
    failures = bool(counts['error'] or counts['fatal'] or reported_failure or 'failed' in terminal_reports)
    status = 'unknown'
    if scan.stable:
        if 'passed' in terminal_reports and failures:
            status = 'conflicting'
        elif failures or (outcome and outcome['value'] == 'failed'):
            status = 'failure_evidence'
        elif outcome and scan.complete and not scan.decode_replacements:
            status = 'reported_pass'
    result = {**scan.metadata(), 'phase_hint': phase, 'status': status,
        'status_scope': 'one log only; not verification signoff',
        'diagnostic_counts': dict(counts), 'reported_uvm_counts': reported_counts,
        'first_error': first_error, 'terminal_report': outcome, 'terminal_reports': terminal_reports,
        'diagnostics': list(groups.values()), 'omitted_diagnostic_events': omitted,
        'tail': list(tail), 'tail_is_file_end': scan.complete,
        'expand_with': 'read_regression_log_range(path, start_line, expected_fingerprint)'}
    return fit_output(result, max_output_chars)


def read_range(root, path, start_line, line_count=40, start_column=0, expected_fingerprint=None,
               max_scan_bytes=DEFAULT_SCAN_BYTES, max_output_chars=12000):
    integer(start_line, 'start_line', 1, 2**31 - 1)
    integer(line_count, 'line_count', 1, 200)
    integer(start_column, 'start_column', 0, MAX_LINE_BYTES)
    integer(max_scan_bytes, 'max_scan_bytes', 1, MAX_SCAN_BYTES)
    integer(max_output_chars, 'max_output_chars', 4000, 32000)
    scan = Scan(resolve_log(root, path), max_scan_bytes)
    if expected_fingerprint is not None and expected_fingerprint != fingerprint(scan.before):
        raise ValueError('stale fingerprint; summarize the current log before expanding')
    rows, used, next_line, next_column = [], 0, start_line, start_column
    end = start_line + line_count
    scan.stop_line = end - 1
    for number, text in scan.rows():
        if start_line <= number < end:
            column = start_column if number == start_line else 0
            if column > len(text):
                raise ValueError('start_column is beyond the selected line')
            item = {'line': number, 'column': column, 'text': text[column:], 'text_truncated': False}
            size = len(json.dumps(item, ensure_ascii=False))
            remaining = max_output_chars - 2000 - used
            if size > remaining:
                # Conservatively budget JSON escaping, and expose an exact continuation cursor.
                available = max(0, remaining // 6 - 100)
                item['text'] = item['text'][:available]
                item['text_truncated'] = True
                next_line, next_column = number, column + len(item['text'])
                scan.stop_line = number
                if not available:
                    continue
            else:
                next_line, next_column = number + 1, 0
            rows.append(item)
            used += len(json.dumps(item, ensure_ascii=False))
    if not scan.stable:
        raise ValueError('log changed while reading; summarize again')
    return {**scan.metadata(), 'start_line': start_line, 'lines': rows,
        'next_line': next_line, 'next_column': next_column,
        'requested_range_complete': next_line >= end or
            (scan.complete and next_line > scan.lines),
        'output_truncated': next_line < min(end, scan.lines + 1),
        'note': 'Resume with next_line and next_column; oversized physical lines stop the scan explicitly.'}
