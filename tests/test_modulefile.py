from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from claude_kit.core import KitError
from claude_kit.modulefile import render_modulefile


class ModulefileTests(unittest.TestCase):
    def _installation(self, root: Path) -> tuple[Path, Path]:
        wrapper = root / "bin" / "claude-kit"
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        wrapper.chmod(0o755)
        python = root / "python"
        python.write_text("", encoding="utf-8")
        python.chmod(0o755)
        return wrapper, python

    def test_render_sets_release_environment_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "installed release"
            _, python = self._installation(root)

            rendered = render_modulefile(root, python)

            self.assertIn("#%Module1.0", rendered)
            self.assertIn("conflict claude_kit", rendered)
            root_text = str(root.resolve()).replace("\\", "\\\\")
            python_text = str(python.resolve()).replace("\\", "\\\\")
            bin_text = str((root / "bin").resolve()).replace("\\", "\\\\")
            self.assertIn(f'CLAUDE_KIT_ROOT "{root_text}"', rendered)
            self.assertIn(f'CLAUDE_KIT_PYTHON "{python_text}"', rendered)
            self.assertIn(f'prepend-path PATH "{bin_text}"', rendered)
            self.assertIn("only changes the shell environment", rendered)
            self.assertIn("does not install", rendered)
            self.assertIn("edit project files", rendered)
            self.assertNotIn("PROJ_DIR", rendered)

    def test_tcl_special_characters_are_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit $ release [one] {two}"
            _, python = self._installation(root)
            python = root / "python $ [one] {two}"
            python.write_text("", encoding="utf-8")
            python.chmod(0o755)

            rendered = render_modulefile(root, python)

            self.assertIn(r"\$", rendered)
            self.assertIn(r"\[", rendered)
            self.assertIn(r"\]", rendered)
            self.assertIn(r"\{", rendered)
            self.assertIn(r"\}", rendered)
            self.assertNotIn("setenv CLAUDE_KIT_ROOT " + str(root), rendered)

    def test_render_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            _, python = self._installation(root)

            self.assertEqual(render_modulefile(root, python), render_modulefile(root, python))

    def test_python_symlink_path_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            self._installation(root)
            base_python = Path(directory) / "base-python"
            base_python.write_text("", encoding="utf-8")
            base_python.chmod(0o755)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            try:
                venv_python.symlink_to(base_python)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"file symlinks are unavailable: {exc}")

            rendered = render_modulefile(root, venv_python)

            lexical_path = str(venv_python.absolute()).replace("\\", "\\\\")
            python_line = next(
                line for line in rendered.splitlines() if line.startswith("setenv CLAUDE_KIT_PYTHON ")
            )
            self.assertEqual(python_line, f'setenv CLAUDE_KIT_PYTHON "{lexical_path}"')
            self.assertNotIn(str(base_python.resolve()), python_line)

    def test_missing_wrapper_or_python_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            python = root / "python"
            python.write_text("", encoding="utf-8")
            python.chmod(0o755)
            with self.assertRaisesRegex(KitError, "claude-kit"):
                render_modulefile(root, python)

            wrapper, _ = self._installation(root)
            wrapper.unlink()
            with self.assertRaisesRegex(KitError, "claude-kit"):
                render_modulefile(root, python)

            _, python = self._installation(root)
            python.unlink()
            with self.assertRaisesRegex(KitError, "python_executable"):
                render_modulefile(root, python)

    def test_control_characters_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit\nrelease"

            with self.assertRaisesRegex(KitError, "control"):
                render_modulefile(root, Path(directory) / "python")


if __name__ == "__main__":
    unittest.main()
