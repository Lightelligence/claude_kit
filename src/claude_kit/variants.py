"""Bounded literal candidate search anchored in one known bug instance."""
from __future__ import annotations

import os
from pathlib import Path

from .artifact_search import search_artifact
from .core import KitError
from .dv import _local_path, _object, _objects, _strings, _text
from .experiment import integer, project, unique


def search(root: Path, profile: dict, plan: dict, *, max_files: int = 200,
           max_scan_bytes: int = 8_000_000, max_matches: int = 100) -> dict:
    project(plan, profile)
    _text(plan.get("id"), "plan.id")
    _text(plan.get("root_cause"), "root_cause")
    scopes = _strings(plan.get("scope"), "scope")
    patterns = _objects(plan.get("patterns"), "patterns")
    if len(patterns) > 8:
        raise KitError("At most eight literal patterns are supported")
    ids, literals = [], []
    for pattern in patterns:
        ids.append(_text(pattern.get("id"), "pattern.id"))
        literals.append(_text(pattern.get("literal"), "pattern.literal"))
        _text(pattern.get("rationale"), "pattern.rationale")
    unique(ids, "pattern IDs")
    unique(literals, "pattern literals")
    integer(max_files, "max_files", 1, 20000)
    integer(max_scan_bytes, "max_scan_bytes", 1, 1_000_000_000)
    integer(max_matches, "max_matches", 1, 1000)
    known = _object(plan.get("known_instance"), "known_instance")
    known_path = _text(known.get("path"), "known_instance.path")
    known_line = integer(known.get("line"), "known_instance.line", 1, 10_000_000)
    normalized_scopes = [_local_path(root, profile, value) for value in scopes]
    known_resolved = _local_path(root, profile, known_path)
    if not any(known_resolved == p or known_resolved.is_relative_to(p) for p in normalized_scopes):
        raise KitError("Known instance must be inside the declared scope")
    anchor = search_artifact(root, _local_path(root, profile, known_path).relative_to(root.resolve()).as_posix(),
                             [literals[0]], max_scan_bytes=min(max_scan_bytes, 1_000_000), max_matches=1000)
    if not any(hit["line_number"] == known_line for hit in anchor["matches"]):
        raise KitError("First pattern must match the known instance at its declared line within the anchor scan budget")
    scanned, matches, gaps, seen = [], [], [], set()
    remaining = max_scan_bytes - anchor["bytes_scanned"]
    stopped = False

    def paths():
        directories_visited = 0
        for scope in normalized_scopes:
            if not scope.exists():
                raise KitError("Variant scope does not exist")
            if scope.is_file():
                yield scope
                continue
            for directory, directories, files in os.walk(scope, followlinks=False):
                directories_visited += 1
                if directories_visited > max_files * 10:
                    gaps.append("directory_traversal_budget_exhausted")
                    return
                directories.sort()
                for name in directories[:]:
                    p = Path(directory) / name
                    if name == ".git" or p.is_symlink():
                        directories.remove(name)
                        gaps.append(f"unscanned_directory:{p.relative_to(root.resolve()).as_posix()}")
                for name in sorted(files):
                    yield Path(directory) / name

    for candidate in paths():
        value = candidate.relative_to(root.resolve()).as_posix()
        if value in seen:
            continue
        seen.add(value)
        if len(seen) > max_files or remaining <= 0 or len(matches) >= max_matches:
            stopped = True
            break
        if candidate.is_symlink():
            gaps.append(f"unscanned_symlink:{value}")
            continue
        try:
            _local_path(root, profile, value)
        except KitError:
            gaps.append(f"forbidden_path:{value}")
            continue
        result = search_artifact(root, value, literals, max_scan_bytes=remaining,
                                 max_matches=max_matches - len(matches))
        remaining -= result["bytes_scanned"]
        scanned.append({"path": value, "scan_complete": result["scan_complete"],
                        "bytes_scanned": result["bytes_scanned"], "sha256": result["sha256"]})
        if not result["scan_complete"] or result["matches_truncated"]:
            gaps.append(f"incomplete_scan:{value}")
        for hit in result["matches"]:
            matches.append({"path": value, "line": hit["line_number"], "pattern_id": ids[hit["query_index"]],
                            "verdict": "unreviewed"})
    if stopped:
        gaps.append("search_budget_exhausted")
    return {"schema_version": 1, "kind": "variant-candidates", "plan_id": plan["id"],
            "search_complete": not gaps, "confirmed_bugs": None, "candidates": matches,
            "scanned_files": scanned, "anchor_bytes_scanned": anchor["bytes_scanned"],
            "total_bytes_scanned": max_scan_bytes - remaining, "gaps": gaps,
            "limitations": ["Literal matches are candidates; inspect semantics and reproduce before classifying a bug.",
                            "No matches do not prove absence. Generalize one pattern element at a time and review noise.",
                            "Completeness covers declared files and literal patterns only, never the entire design."]}
