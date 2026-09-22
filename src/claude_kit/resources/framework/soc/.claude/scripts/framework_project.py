"""Resolve consumer roots independently of the shared script's physical path."""
import os
from pathlib import Path


def project_root():
    selected = os.environ.get('PROJ_DIR')
    if selected is not None:
        path = Path(selected)
        if not selected or not path.is_absolute() or not path.is_dir():
            raise ValueError('PROJ_DIR must select an existing absolute project directory')
        candidates = [path.resolve()]
    else:
        cwd = Path.cwd().resolve()
        candidates = [cwd, *cwd.parents]
    for path in candidates:
        if any((path / name).is_file() for name in ('.claude/project.toml', '.claude/project.json', '.ai/project.toml', '.ai/project.json')):
            return path
    raise ValueError('No project profile found; run from the consumer checkout or set PROJ_DIR')


def instruction_text(path, root, seen=None):
    """Expand standalone local @imports for budget/contract checks; fail closed."""
    import re
    root = Path(root).resolve()
    path = Path(path).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError('Instruction import escapes project root')
    seen = set() if seen is None else seen
    if path in seen:
        return ''
    seen.add(path)
    text = path.read_text(encoding='utf-8')
    parts = [text]
    if path.suffix != '.md':
        return text
    fence = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(('```', '~~~')):
            marker = stripped[:3]
            fence = None if fence == marker else (marker if fence is None else fence)
            continue
        match = re.fullmatch(r'@([^\s]+)\s*', stripped) if fence is None else None
        if match:
            parts.append(instruction_text(path.parent / match.group(1), root, seen))
    return '\n'.join(parts)
