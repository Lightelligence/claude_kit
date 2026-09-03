"""Render an Environment Modules modulefile for an installed claude_kit."""

from __future__ import annotations

import os
from pathlib import Path

from .core import KitError


def _validate_tcl_value(value: str, label: str) -> None:
    """Reject characters that could make a generated modulefile ambiguous."""

    if any(ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in value):
        raise KitError(f"{label} must not contain newline or control characters")


def _path_value(value: Path, label: str, *, resolve_symlinks: bool = True) -> Path:
    try:
        path = Path(value)
    except (TypeError, ValueError, OSError) as exc:
        raise KitError(f"{label} must be a valid filesystem path") from exc

    _validate_tcl_value(str(path), label)
    try:
        resolved = path.resolve() if resolve_symlinks else Path(os.path.abspath(path))
    except (OSError, RuntimeError) as exc:
        action = "resolve" if resolve_symlinks else "make absolute"
        raise KitError(f"Cannot {action} {label}: {path}") from exc
    _validate_tcl_value(str(resolved), label)
    return resolved


def _require_executable(path: Path, label: str) -> None:
    try:
        is_executable = path.is_file() and os.access(path, os.X_OK)
    except OSError as exc:
        raise KitError(f"Cannot inspect {label}: {path}") from exc
    if not is_executable:
        raise KitError(f"{label} does not exist or is not executable: {path}")


def _tcl_quote(value: str, label: str = "modulefile value") -> str:
    """Return a Tcl double-quoted word with substitutions escaped."""

    _validate_tcl_value(value, label)
    escapes = {
        "\\": "\\\\",
        '"': '\\"',
        "$": "\\$",
        "[": "\\[",
        "]": "\\]",
        "{": "\\{",
        "}": "\\}",
    }
    return '"' + "".join(escapes.get(character, character) for character in value) + '"'


def render_modulefile(kit_root: Path, python_executable: Path) -> str:
    """Render a deterministic modulefile for one installed kit release.

    The generated module changes only shell environment state.  It does not
    install the kit, edit a project, or infer a path from this source checkout.
    """

    root = _path_value(kit_root, "kit_root")
    # Keep a venv's lexical bin/python path: resolving it would replace the
    # venv interpreter with its base interpreter and lose its package set.
    python = _path_value(python_executable, "python_executable", resolve_symlinks=False)
    wrapper = root / "bin" / "claude-kit"
    _require_executable(wrapper, "kit_root/bin/claude-kit")
    _require_executable(python, "python_executable")

    lines = [
        "#%Module1.0",
        "# Generated for one installed claude_kit release.",
        "",
        "proc ModulesHelp { } {",
        '    puts stderr "claude_kit: shell environment only for this installed release."',
        '    puts stderr "This module only changes the shell environment; it does not install claude_kit or edit project files."',
        "}",
        'module-whatis "claude_kit: shell environment only; does not install or edit project files."',
        "conflict claude_kit",
        f"setenv CLAUDE_KIT_ROOT {_tcl_quote(str(root), 'kit_root')}",
        f"setenv CLAUDE_KIT_PYTHON {_tcl_quote(str(python), 'python_executable')}",
        f"prepend-path PATH {_tcl_quote(str(root / 'bin'), 'kit_root/bin')}",
        "",
    ]
    return "\n".join(lines)
