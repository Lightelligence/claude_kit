"""License-free tests for the project xwiki validator."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / ".claude/skills/xwiki/scripts/validate_xwiki.py"
INITIALIZER = ROOT / ".claude/skills/xwiki/scripts/init_xwiki.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _initialized_wiki(tmp_path: Path):
    init = _load("xin_xwiki_init", INITIALIZER)
    wiki = tmp_path / "wiki"
    assert init.main(["--wiki-dir", str(wiki)]) == 0
    return _load("xin_xwiki_validate", VALIDATOR), wiki


def test_validator_ignores_hidden_markdown_and_nested_directories(tmp_path: Path) -> None:
    validate, wiki = _initialized_wiki(tmp_path)
    hidden = wiki / ".git/objects/nested"
    hidden.mkdir(parents=True)
    (hidden / "poison.md").write_text("not frontmatter\n", encoding="utf-8")
    cache = wiki / "dv/.cache/nested"
    cache.mkdir(parents=True)
    (cache / "poison.md").write_text("not frontmatter\n", encoding="utf-8")
    assert validate.validate_wiki(wiki) == []


def test_validator_rejects_hidden_links_without_probing(tmp_path: Path, monkeypatch) -> None:
    validate, wiki = _initialized_wiki(tmp_path)
    page = wiki / "dv/hidden-link.md"
    page.write_text(
        "---\ntype: Topic\ntitle: Hidden link\ndescription: test\n"
        "object_type: dv\n---\n[metadata](../.git/config)\n",
        encoding="utf-8",
    )

    def guarded_probe(root: Path, source: Path, target: str) -> bool:
        assert ".git" not in target
        return True

    monkeypatch.setattr(validate, "_link_exists", guarded_probe)
    findings = validate.validate_wiki(wiki)
    assert any(finding.code == "LINK_HIDDEN_PATH" for finding in findings)


def test_validator_keeps_visible_nested_directory_requirements(tmp_path: Path) -> None:
    validate, wiki = _initialized_wiki(tmp_path)
    nested = wiki / "dv/new_topic"
    nested.mkdir()
    (nested / "page.md").write_text(
        "---\ntype: Topic\ntitle: Page\ndescription: test\nobject_type: dv\n---\n",
        encoding="utf-8",
    )
    missing = {
        finding.path
        for finding in validate.validate_wiki(wiki)
        if finding.code == "DIR_INDEX_LOG_MISSING"
    }
    assert {"dv/new_topic/index.md", "dv/new_topic/log.md"} <= missing


def test_validator_rejects_visible_markdown_symlink(tmp_path: Path) -> None:
    validate, wiki = _initialized_wiki(tmp_path)
    hidden = wiki / ".git"
    hidden.mkdir()
    secret = hidden / "config"
    secret.write_text("must not be parsed\n", encoding="utf-8")
    (wiki / "dv/leak.md").symlink_to(secret)

    findings = validate.validate_wiki(wiki)
    assert any(
        finding.code == "SYMLINK_FORBIDDEN" and finding.path == "dv/leak.md"
        for finding in findings
    )
    assert not any(
        finding.code == "FRONTMATTER_MISSING" and finding.path == "dv/leak.md"
        for finding in findings
    )


def test_validator_does_not_probe_link_through_visible_symlink(
    tmp_path: Path,
) -> None:
    validate, wiki = _initialized_wiki(tmp_path)
    hidden = wiki / ".git"
    hidden.mkdir()
    (hidden / "config").write_text("secret\n", encoding="utf-8")
    (wiki / "dv/alias").symlink_to(hidden, target_is_directory=True)
    page = wiki / "dv/link.md"
    page.write_text(
        "---\ntype: Topic\ntitle: Link\ndescription: test\n"
        "object_type: dv\n---\n[metadata](alias/config)\n",
        encoding="utf-8",
    )

    findings = validate.validate_wiki(wiki)
    assert any(
        finding.code == "SYMLINK_FORBIDDEN" and finding.path == "dv/alias"
        for finding in findings
    )
    assert any(
        finding.code == "LINK_BROKEN" and finding.path == "dv/link.md"
        for finding in findings
    )


def test_validator_rejects_required_structure_symlink(tmp_path: Path) -> None:
    validate, wiki = _initialized_wiki(tmp_path)
    original = wiki / "de"
    replacement = wiki / "visible_de"
    original.rename(replacement)
    original.symlink_to(wiki / ".git", target_is_directory=True)

    findings = validate.validate_wiki(wiki)
    assert any(
        finding.code == "REQUIRED_DIR_MISSING" and finding.path == "de"
        for finding in findings
    )


def test_file_hook_blocks_symlinked_wiki_target(tmp_path: Path, monkeypatch) -> None:
    validate, wiki = _initialized_wiki(tmp_path)
    hidden = wiki / ".git"
    hidden.mkdir()
    target = wiki / "dv/leak.md"
    target.symlink_to(hidden / "config")
    payloads = []

    monkeypatch.setenv("XWIKI_DIR", str(wiki))
    monkeypatch.setattr(
        validate,
        "_read_stdin_json",
        lambda: {"tool_input": {"file_path": str(target)}},
    )
    monkeypatch.setattr(validate, "_print_claude_file", payloads.append)

    assert validate.main(["--root", str(tmp_path), "--hook", "claude-file"]) == 0
    assert payloads and not payloads[0]["ok"]
    assert any(
        finding["code"] == "SYMLINK_FORBIDDEN"
        for finding in payloads[0]["errors"]
    )
