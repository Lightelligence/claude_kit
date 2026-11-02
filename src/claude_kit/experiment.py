"""Shared, read-only records for skill experiments and fix validation.

Collectors own execution and extraction. These helpers check declared inputs
and artifact integrity, not whether a collector told the truth.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from .core import KitError, MAX_ARTIFACT_BYTES
from .dv import _digest, _local_path, _object, _objects, _strings, _text


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise KitError(f"{label} must be a lowercase SHA-256 digest")
    return value


def integer(value: Any, label: str, minimum: int = 0, maximum: int = 10000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise KitError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def version(document: dict) -> None:
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise KitError("schema_version must be 1")


def unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise KitError(f"Duplicate {label}")


def read_bytes(root: Path, profile: dict, value: str) -> bytes:
    path = _local_path(root, profile, value)
    if not path.is_file():
        raise KitError(f"Missing regular file: {value}")
    with path.open("rb") as stream:
        data = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise KitError(f"Document exceeds {MAX_ARTIFACT_BYTES} bytes: {value}")
    return data


def parse_json(data: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise KitError("Duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise KitError("Non-finite JSON number")

    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
        # Reject exponent overflow as well as NaN/Infinity literals.
        json.dumps(result, allow_nan=False)
        return result
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise KitError("Invalid UTF-8 JSON document") from exc


def load(root: Path, profile: dict, value: str) -> dict:
    return _object(parse_json(read_bytes(root, profile, value)), "document")


def project(document: dict, profile: dict) -> None:
    version(document)
    if not document.get("project") or document["project"] != profile.get("project", {}).get("id"):
        raise KitError("project must match profile project.id")


def scope_snapshot(root: Path, profile: dict, inputs: list[str]) -> dict:
    _strings(inputs, "inputs", empty=True)
    root = root.resolve()
    files = {}
    for value in inputs:
        path = _local_path(root, profile, value)
        if not path.exists():
            raise KitError(f"Missing input: {value}")
        if (root / value).is_symlink():
            raise KitError("Use real input paths instead of symlinks")
        candidates = path.rglob("*") if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_symlink():
                raise KitError("Symlinks in experiment input trees are unsupported")
            relative = candidate.relative_to(root).as_posix()
            checked = _local_path(root, profile, relative)
            if not checked.is_file():
                continue
            if len(files) >= 20000 and relative not in files:
                raise KitError("Input scope exceeds 20000 files")
            files[relative] = _digest(checked)
    if inputs and not files:
        raise KitError("Declared inputs contain no regular files")
    revision = None
    if (root / ".git").exists():
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=10, check=False)
        if result.returncode == 0:
            revision = result.stdout.strip()
    return {"input_digest": digest(files), "source_revision": revision, "files": dict(sorted(files.items()))}


def baseline(value: Any) -> dict:
    value = _object(value, "baseline")
    sha(value.get("input_digest"), "baseline.input_digest")
    if "source_revision" not in value or (value["source_revision"] is not None and
                                           (not isinstance(value["source_revision"], str) or not value["source_revision"].strip())):
        raise KitError("baseline.source_revision must be a string or null")
    return value


def artifact(root: Path, profile: dict, ref: Any, *, bounded: bool = False) -> tuple[list[str], bytes | None]:
    ref = _object(ref, "artifact")
    value = _text(ref.get("path"), "artifact.path")
    expected = sha(ref.get("sha256"), "artifact.sha256")
    path = _local_path(root, profile, value)
    if not path.is_file():
        return [f"missing_artifact:{value}"], None
    data = read_bytes(root, profile, value) if bounded else None
    actual = hashlib.sha256(data).hexdigest() if bounded else _digest(path)
    if actual != expected:
        return [f"changed_artifact:{value}"], None
    return [], data


def artifacts(root: Path, profile: dict, refs: Any) -> list[str]:
    return [gap for ref in _objects(refs, "artifacts") for gap in artifact(root, profile, ref)[0]]


def markdown(result: dict, title: str) -> str:
    """Render the same evidence and limitations as JSON without hiding gaps."""
    return f"# {title}\n\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```\n"


def metric(value: Any, name: str) -> int | float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not 0 <= value <= 1e18 or not math.isfinite(value):
        raise KitError(f"{name} must be a finite non-negative number or null")
    if name in ("tokens", "tool_calls") and type(value) is not int:
        raise KitError(f"{name} must be an integer or null")
    return value
