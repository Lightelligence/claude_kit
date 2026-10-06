"""Bounded, read-only literal searches over project artifacts."""

from __future__ import annotations

import bisect
import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from .core import KitError, _project_path

_CHUNK_BYTES = 16_384
_MAX_LINE_BYTES = 65_536
_SNIPPET_BYTES = 256
_MAX_QUERY_BYTES = 4096


def _budget(name: str, value: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise KitError(f"{name} must be a non-negative integer")
    if value > maximum:
        raise KitError(f"{name} must not exceed {maximum}")


def _version(value: os.stat_result) -> dict[str, int]:
    return {"bytes": value.st_size, "mtime_ns": value.st_mtime_ns, "inode": value.st_ino}


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    # Windows' legacy st_ctime can differ between stat and fstat for an
    # unchanged file. Use the same version fields as read_artifact plus device.
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _safe_prefix(data: bytes, line_bytes: int) -> tuple[bytes, int, bool]:
    """Stop before a line exceeds the fixed memory/scan guard."""
    start = 0
    while start < len(data):
        newline = data.find(b"\n", start)
        end = len(data) if newline < 0 else newline
        length = end - start
        if line_bytes + length > _MAX_LINE_BYTES:
            return data[:start + _MAX_LINE_BYTES - line_bytes], _MAX_LINE_BYTES, True
        line_bytes += length
        if newline < 0:
            break
        line_bytes = 0
        start = newline + 1
    return data, line_bytes, False


def search_artifact(
    root: Path,
    relative_path: str,
    queries: list[str],
    max_output_bytes: int = 16_384,
    max_matches: int = 40,
    max_scan_bytes: int = 64 * 1024 * 1024,
) -> dict[str, Any]:
    """Search literal UTF-8 bytes once; counts include overlapping occurrences.

    The output budget applies to the aggregate UTF-8 snippet text, not JSON
    metadata. Hit records, query size and line length have separate hard caps.
    Counts describe only the scanned prefix when scan_complete is false. A
    zero count has no verification/PASS meaning. Original bytes remain available
    through read_artifact; snippets may replace invalid or split UTF-8 bytes.
    """
    _budget("max_output_bytes", max_output_bytes, 1_000_000)
    _budget("max_matches", max_matches, 1000)
    _budget("max_scan_bytes", max_scan_bytes, 1024 * 1024 * 1024)
    if not isinstance(queries, (list, tuple)) or not 1 <= len(queries) <= 8:
        raise KitError("queries must contain between 1 and 8 literal strings")
    encoded = []
    for query in queries:
        if not isinstance(query, str) or not query or len(query) > _MAX_QUERY_BYTES:
            raise KitError("each query must be a non-empty string of at most 4096 UTF-8 bytes")
        try:
            needle = query.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise KitError("queries must be valid UTF-8 strings") from exc
        if len(needle) > _MAX_QUERY_BYTES:
            raise KitError("each query must be at most 4096 UTF-8 bytes")
        encoded.append(needle)

    path = _project_path(root, relative_path, "artifact path")
    if not path.is_file():
        raise KitError(f"Artifact does not exist: {relative_path}")
    records = [{"query": query, "count": 0, "matches_returned": 0} for query in queries]
    matches: list[dict[str, Any]] = []
    next_starts = [0] * len(encoded)
    tail = b""
    overlap = max(map(len, encoded)) - 1
    bytes_read = bytes_scanned = output_bytes = line_bytes = newlines_seen = 0
    digest = hashlib.sha256()
    stop_reason = None
    output_truncated = matches_truncated = False

    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise KitError("Artifact must be a regular file")
            scan_limit = min(max_scan_bytes, before.st_size)
            while bytes_read < scan_limit:
                data = stream.read(min(_CHUNK_BYTES, scan_limit - bytes_read))
                if not data:
                    stop_reason = "short_read"
                    break
                bytes_read += len(data)
                data, line_bytes, too_long = _safe_prefix(data, line_bytes)
                window = tail + data
                window_start = bytes_scanned - len(tail)
                window_line = newlines_seen - tail.count(b"\n") + 1
                newline_positions = [index for index, byte in enumerate(window) if byte == 10]
                for query_index, needle in enumerate(encoded):
                    cursor = max(0, next_starts[query_index] - window_start)
                    while True:
                        position = window.find(needle, cursor)
                        if position < 0:
                            break
                        cursor = position + 1
                        records[query_index]["count"] += 1
                        if len(matches) >= max_matches:
                            matches_truncated = True
                            continue
                        remaining = max_output_bytes - output_bytes
                        snippet_start = max(0, position - 64)
                        snippet_end = min(len(window), snippet_start + _SNIPPET_BYTES)
                        raw = window[snippet_start:snippet_end]
                        try:
                            text = raw.decode("utf-8")
                            encoding = "utf-8"
                        except UnicodeDecodeError:
                            text = raw.decode("utf-8", errors="replace")
                            encoding = "utf-8-replace"
                        # Clip at Unicode boundaries; replacement glyphs can be
                        # larger than their original bytes. Never exceed total.
                        clipped = text.encode("utf-8")[:remaining].decode("utf-8", errors="ignore")
                        budget_clipped = clipped != text
                        output_truncated |= budget_clipped
                        output_bytes += len(clipped.encode("utf-8"))
                        matches.append({
                            "query_index": query_index,
                            "byte_offset": window_start + position,
                            "line_number": window_line + bisect.bisect_left(newline_positions, position),
                            "text": clipped,
                            "text_encoding": encoding,
                            "snippet_start": window_start + snippet_start,
                            "snippet_end": window_start + snippet_end,
                            "snippet_truncated": budget_clipped or snippet_start > 0 or snippet_end < len(window)
                            or window_start > 0 or bytes_scanned + len(data) < before.st_size,
                        })
                        records[query_index]["matches_returned"] += 1
                    next_starts[query_index] = window_start + max(cursor, len(window) - len(needle) + 1)
                digest.update(data)
                bytes_scanned += len(data)
                newlines_seen += data.count(b"\n")
                tail = window[-overlap:] if overlap else b""
                if too_long:
                    stop_reason = "line_too_long"
                    break
            after = os.fstat(stream.fileno())
        # Also detect replacement/unlink of the path while the original fd was
        # read. An unchanged fd alone cannot establish current-path identity.
        try:
            current = path.stat()
        except OSError:
            current = None
    except OSError as exc:
        raise KitError(f"Cannot search artifact {relative_path}: {exc}") from exc

    changed = _identity(before) != _identity(after) or current is None or _identity(before) != _identity(current)
    if stop_reason is None and bytes_scanned < before.st_size:
        stop_reason = "scan_byte_limit"
    if changed and stop_reason is None:
        stop_reason = "changed_during_read"
    complete = stop_reason is None and bytes_scanned == before.st_size
    snippet_truncated = any(match["snippet_truncated"] for match in matches)
    return {
        "path": path.relative_to(root.resolve()).as_posix(),
        "file_version": _version(before),
        "sha256": digest.hexdigest() if complete else None,
        "changed_during_read": changed,
        "scan_complete": complete,
        "scan_stop_reason": stop_reason,
        "bytes_read": bytes_read,
        "bytes_scanned": bytes_scanned,
        "queries": records,
        "matches": matches,
        "output_bytes": output_bytes,
        "matches_truncated": matches_truncated,
        "output_truncated": output_truncated,
        "truncated": not complete or matches_truncated or output_truncated or snippet_truncated,
        "limits": {"max_output_bytes": max_output_bytes, "max_matches": max_matches,
                   "max_scan_bytes": max_scan_bytes, "max_line_bytes": _MAX_LINE_BYTES,
                   "max_snippet_bytes": _SNIPPET_BYTES},
    }
