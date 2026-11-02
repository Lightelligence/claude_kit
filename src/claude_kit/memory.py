"""Bounded, project-owned task checkpoints; never a transcript store."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .core import KitError

MAX_STATE_BYTES = 4096
MAX_STATE_LINES = 50
STATE_ROOT = ".claude/task-memory"
SECTIONS = ("Objective", "Constraints", "Decisions", "Progress", "Evidence", "Next")
MAX_SETTINGS_BYTES = 256 * 1024


def _linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def _path(root: Path, relative: str) -> Path:
    root = root.resolve(strict=True)
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise KitError("Memory path must stay inside the project")
    target = root / value
    for part in (target, *target.parents):
        if part == root:
            break
        if part.exists() or part.is_symlink():
            if _linked(part):
                raise KitError("Memory paths must not traverse links or junctions")
            if part != target and not part.is_dir():
                raise KitError("Memory parent must be a directory")
    if not target.resolve().is_relative_to(root):
        raise KitError("Memory path escapes the project")
    return target


def task_path(root: Path, task: str) -> Path:
    if not isinstance(task, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", task) or len(task) > 64:
        raise KitError("Task must be a lowercase slug of at most 64 characters")
    if task.split('.')[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise KitError("Task is a reserved Windows name")
    return _path(root, f"{STATE_ROOT}/{task}/STATE.md")


def _read(path: Path, limit: int) -> bytes:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise KitError("Memory input must be a regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise KitError("Memory input must be a regular file")
        value = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    signature = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
    if signature(before) != signature(after) or signature(after) != signature(path.stat()):
        raise KitError("Memory file changed while reading; retry")
    if len(value) > limit:
        raise KitError(f"Memory input exceeds {limit} bytes; move details to referenced artifacts")
    return value


def validate_state(data: bytes) -> str:
    if len(data) > MAX_STATE_BYTES:
        raise KitError(f"Task state exceeds {MAX_STATE_BYTES} UTF-8 bytes")
    text = data.decode('utf-8')
    if len(text.splitlines()) > MAX_STATE_LINES:
        raise KitError(f"Task state exceeds {MAX_STATE_LINES} lines")
    if any(ord(char) < 32 and char not in '\r\n\t' for char in text):
        raise KitError("Task state contains control characters")
    headings = set(text.splitlines())
    missing = [name for name in SECTIONS if f"## {name}" not in headings]
    if missing:
        raise KitError("Task state is missing sections: " + ', '.join(missing))
    return text


def _result(root: Path, path: Path, data: bytes) -> dict:
    text = validate_state(data)
    return {"path": path.relative_to(root.resolve()).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "lines": len(text.splitlines()), "content": text,
            "evidence": "Checkpoint claims require source/run verification; this is not a PASS result"}


@contextmanager
def _lock(root: Path, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    _path(root, path.relative_to(root.resolve()).as_posix())
    key = hashlib.sha256(path.relative_to(root.resolve()).as_posix().encode()).hexdigest()
    relative = f'.claude/.runtime/task-memory-locks/{key}.lock'
    lock_path = _path(root, relative)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _path(root, relative)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0), 0o600)
    acquired = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise KitError("Memory lock must be a regular file")
        if os.fstat(fd).st_size == 0:
            os.write(fd, b'\0')
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise KitError("Memory file is locked; retry after its writer finishes") from exc
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _replace(path: Path, data: bytes, expected: bytes | None) -> None:
    fd, name = tempfile.mkstemp(prefix='.memory-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if expected is None:
            try:
                os.link(name, path)
            except FileExistsError as exc:
                raise KitError("Memory target changed before creation; read it first") from exc
        else:
            try:
                current = _read(path, len(expected))
            except (OSError, KitError) as exc:
                raise KitError("Memory target changed while preparing the update") from exc
            if current != expected:
                raise KitError("Memory target changed while preparing the update")
            os.chmod(name, stat.S_IMODE(path.stat().st_mode))
            os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def init_state(root: Path, task: str) -> dict:
    path = task_path(root, task)
    data = ('# Task: ' + task + '\n\n' + '\n\n'.join(f'## {name}\nNot recorded.' for name in SECTIONS) + '\n').encode('utf-8')
    with _lock(root, path):
        if path.exists():
            raise KitError("Task state already exists; read it and use a checked checkpoint")
        _replace(path, data, None)
    return _result(root, path, data)


def read_state(root: Path, task: str) -> dict:
    path = task_path(root, task)
    return _result(root, path, _read(path, MAX_STATE_BYTES))


def checkpoint(root: Path, task: str, data: bytes, expected_sha256: str) -> dict:
    validate_state(data)
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise KitError("A previous read's SHA256 is required")
    path = task_path(root, task)
    with _lock(root, path):
        current = _read(path, MAX_STATE_BYTES)
        if hashlib.sha256(current).hexdigest() != expected_sha256:
            raise KitError("Task state changed; read and reconcile it before writing")
        _replace(path, data, current)
    return _result(root, path, data)


def read_input(root: Path, relative: str) -> bytes:
    return _read(_path(root, relative), MAX_STATE_BYTES)


def memory_status(root: Path) -> dict:
    settings = {}
    for relative in ('.claude/settings.json', '.claude/settings.local.json'):
        path = _path(root, relative)
        if path.exists():
            value = json.loads(_read(path, MAX_SETTINGS_BYTES))
            if not isinstance(value, dict):
                raise KitError("Claude settings must be an object")
            if 'autoMemoryEnabled' in value and type(value['autoMemoryEnabled']) is not bool:
                raise KitError("autoMemoryEnabled must be a boolean")
            settings[relative] = {"autoMemoryEnabled": value.get('autoMemoryEnabled'),
                                  "custom_memory_directory": bool(value.get('autoMemoryDirectory'))}
    return {"project_settings": settings, "state_root": STATE_ROOT,
            "max_state_bytes": MAX_STATE_BYTES, "max_state_lines": MAX_STATE_LINES,
            "native_activation": "Unverified: check /memory in the actual client; user, environment and managed settings also apply"}


def enable_auto_memory(root: Path) -> dict:
    """Add only an absent project key; preserve explicit choices and other bytes."""
    path = _path(root, '.claude/settings.json')
    with _lock(root, path):
        previous = _read(path, MAX_SETTINGS_BYTES) if path.exists() else None
        raw = previous if previous is not None else b'{}\n'
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise KitError("Claude settings must be an object")
        if 'autoMemoryEnabled' in value:
            if type(value['autoMemoryEnabled']) is not bool:
                raise KitError("autoMemoryEnabled must be a boolean")
            return {"changed": False, "autoMemoryEnabled": value['autoMemoryEnabled'],
                    "preserved_explicit_setting": True}
        text = raw.decode('utf-8')
        end = text.rfind('}')
        newline = '\r\n' if '\r\n' in text else '\n'
        prefix = text[:end].rstrip() + (',' if value else '')
        updated = (prefix + newline + '  "autoMemoryEnabled": true' + newline + text[end:]).encode('utf-8')
        assert json.loads(updated) == {**value, 'autoMemoryEnabled': True}
        _replace(path, updated, previous)
    return {"changed": True, "autoMemoryEnabled": True,
            "native_activation": "Check /memory in the actual client; overrides may still apply"}
