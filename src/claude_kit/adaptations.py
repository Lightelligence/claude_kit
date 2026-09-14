"""Explicit, revision-locked source adaptation; never activate or execute it."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .core import KitError, resource_root
from .upstream import (
    _is_link, _real_directory, _safe_relative, _source_inventory,
    bundled_snapshot, inspect_snapshot,
)


def bundled_patches() -> Path:
    return resource_root() / "adaptations/vibe_soc/patches.json"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replacements(snapshot: Path, manifest: dict[str, Any], patch: dict[str, Any]) -> dict[str, bytes]:
    if (not isinstance(patch, dict) or patch.get("schema_version") != 1
            or patch.get("upstream_commit") != manifest["commit"]
            or not isinstance(patch.get("files"), list) or not patch["files"]):
        raise KitError("Adaptations do not match this upstream revision; review and rebase them")
    result = {}
    for entry in patch["files"]:
        if not isinstance(entry, dict):
            raise KitError("Invalid adaptation entry")
        name = entry.get("path")
        _safe_relative(name)
        if name in result or name not in manifest["files"]:
            raise KitError("Adaptation must name a unique existing snapshot file")
        original = (snapshot / "source" / name).read_bytes()
        if not (entry.get("before_sha256") == manifest["files"][name]["sha256"] == _digest(original)):
            raise KitError(f"Adaptation base mismatch: {name}")
        try:
            content = original.decode("utf-8")
        except UnicodeError as exc:
            raise KitError("Adaptations require UTF-8 text") from exc
        hunks = entry.get("hunks")
        if not isinstance(hunks, list) or not hunks:
            raise KitError("Adaptation hunks are missing")
        for hunk in hunks:
            if not isinstance(hunk, dict):
                raise KitError("Invalid adaptation hunk")
            for key in ("before", "after"):
                lines = hunk.get(key)
                if (not isinstance(lines, list) or
                        any(not isinstance(line, str) or "\n" in line or "\r" in line for line in lines)):
                    raise KitError("Adaptation hunks must contain individual text lines")
            before = "\n".join(hunk["before"]) + "\n"
            after = "\n".join(hunk["after"]) + "\n" if hunk["after"] else ""
            if not hunk["before"] or content.count(before) != 1:
                raise KitError(f"Adaptation context is missing or ambiguous: {name}")
            content = content.replace(before, after, 1)
        data = content.encode("utf-8")
        if _digest(data) != entry.get("after_sha256"):
            raise KitError(f"Adaptation result hash mismatch: {name}")
        result[name] = data
    return result


def export_adapted(output: Path) -> dict[str, Any]:
    """Write a NEW directory with source/ and separate adaptation provenance.

    No project configuration is changed. Refuse links and existing destinations.
    On an I/O failure, retain partial output for inspection; success is marked
    only by the final adaptation.json. The caller must use an idle destination.
    """
    snapshot = bundled_snapshot()
    manifest = inspect_snapshot(snapshot)
    patch_path = bundled_patches()
    _real_directory(patch_path.parent)
    if _is_link(patch_path):
        raise KitError("Adaptation manifest must not be a link")
    patch_bytes = patch_path.read_bytes()
    try:
        patch = json.loads(patch_bytes)
    except (ValueError, UnicodeError) as exc:
        raise KitError("Cannot read adaptation manifest") from exc
    replacements = _replacements(snapshot, manifest, patch)
    output = output.absolute()
    _real_directory(output.parent)
    if _is_link(output) or output.exists():
        raise KitError("Adapted output must be a new directory; existing data is never replaced")
    if output.resolve().is_relative_to(snapshot.resolve()):
        raise KitError("Adapted output must be outside the pristine snapshot")
    output.mkdir()  # atomic reservation; parent must already exist
    source = output / "source"
    source.mkdir()
    expected = {}
    for name, info in manifest["files"].items():
        original = (snapshot / "source" / name).read_bytes()
        if _digest(original) != info["sha256"]:
            raise KitError(f"Snapshot changed during export: {name}")
        data = replacements.get(name, original)
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        if os.name != "nt":
            target.chmod(0o755 if info["git_mode"] == "100755" else 0o644)
        expected[name] = {"sha256": _digest(data), "size": len(data)}
    if _source_inventory(source) != expected:
        raise KitError("Adapted export verification failed; output has been retained")
    record = {
        "schema_version": 1, "status": "exported_not_activated",
        "upstream_url": manifest["upstream_url"], "upstream_commit": manifest["commit"],
        "patch_sha256": _digest(patch_bytes), "adapted_files": sorted(replacements),
        "files": expected, "functional_validation": "not_run",
    }
    with (output / "adaptation.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return {key: value for key, value in record.items() if key != "files"} | {"output": str(output)}
