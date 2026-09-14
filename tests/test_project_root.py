from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_project"
ENTRY = ROOT / "bin" / "claude-kit"
sys.path.insert(0, str(ROOT / "src"))

from claude_kit.core import KitError, resolve_project_root


@contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _environment(project_root: Path | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    if project_root is None:
        environment.pop("PROJ_DIR", None)
    else:
        environment["PROJ_DIR"] = str(project_root)
    return environment


def _make_checkout(parent: Path, name: str, project_id: str) -> Path:
    project = parent / name
    shutil.copytree(FIXTURE, project)
    (project / ".git").mkdir()
    profile = project / ".ai" / "project.toml"
    profile.write_text(
        profile.read_text(encoding="utf-8").replace(
            'id = "minimal_fixture"',
            f'id = "{project_id}"',
        ),
        encoding="utf-8",
        newline="\n",
    )
    return project


class ResolveProjectRootTests(unittest.TestCase):
    def test_explicit_root_is_exact_and_does_not_discover_an_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "checkout"
            (checkout / ".git").mkdir(parents=True)
            nested = checkout / "nested"
            nested.mkdir()

            with patch.dict(os.environ):
                os.environ.pop("PROJ_DIR", None)
                self.assertEqual(resolve_project_root(nested), nested.resolve())
                with self.assertRaises(KitError):
                    resolve_project_root(checkout / "not-created")

    def test_invalid_project_dir_fails_closed_without_discovery_or_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            discoverable = root / "discoverable"
            (discoverable / ".git").mkdir(parents=True)
            project_file = root / "project-file"
            project_file.write_text("not a directory", encoding="utf-8")
            values = {
                "empty": "",
                "relative": "relative-project",
                "missing": str(root / "missing-project"),
                "file": str(project_file),
            }
            for label, value in values.items():
                with self.subTest(value=label):
                    with patch.dict(os.environ):
                        os.environ["PROJ_DIR"] = value
                        with patch(
                            "claude_kit.core.find_project_root",
                            side_effect=AssertionError("invalid PROJ_DIR must not fall back"),
                        ) as discover:
                            with self.assertRaises(KitError):
                                resolve_project_root()
                            discover.assert_not_called()

    def test_valid_explicit_root_ignores_invalid_stale_project_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / "explicit project"
            explicit.mkdir()
            with patch.dict(os.environ):
                os.environ["PROJ_DIR"] = str(root / "stale-project")
                before = dict(os.environ)
                self.assertEqual(resolve_project_root(explicit), explicit.resolve())
                self.assertEqual(dict(os.environ), before)

    def test_project_dir_is_not_mutated_and_unset_value_discovers_from_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            (checkout / ".git").mkdir(parents=True)
            nested = checkout / "tools" / "runner"
            nested.mkdir(parents=True)
            with patch.dict(os.environ):
                os.environ.pop("PROJ_DIR", None)
                before = dict(os.environ)
                with _working_directory(nested):
                    self.assertEqual(resolve_project_root(), checkout.resolve())
                self.assertEqual(dict(os.environ), before)

    def test_variable_substitution_supports_exact_and_suffix_paths_without_shell_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "checkout with spaces"
            root.mkdir()
            literal_suffix = root / "literal $(echo no-shell)"
            literal_suffix.mkdir()
            with patch.dict(os.environ):
                os.environ["PROJ_DIR"] = str(root)
                before = dict(os.environ)
                for token in ("$PROJ_DIR", "${PROJ_DIR}"):
                    with self.subTest(token=token, suffix=False):
                        self.assertEqual(resolve_project_root(token), root.resolve())
                    with self.subTest(token=token, suffix=True):
                        self.assertEqual(
                            resolve_project_root(f"{token}/literal $(echo no-shell)"),
                            literal_suffix.resolve(),
                        )
                self.assertEqual(dict(os.environ), before)

                os.environ.pop("PROJ_DIR")
                for token in ("$PROJ_DIR", "${PROJ_DIR}"):
                    with self.subTest(token=token, unset=True):
                        with self.assertRaisesRegex(KitError, "PROJ_DIR"):
                            resolve_project_root(token)

    def test_symlink_directory_resolves_to_canonical_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "real checkout"
            target.mkdir()
            alias = root / "checkout alias"
            try:
                alias.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")
            self.assertEqual(resolve_project_root(alias), target.resolve())


class ProjectRootCliTests(unittest.TestCase):
    def run_cli(
        self,
        *args: str,
        cwd: Path,
        environment: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ENTRY), *args],
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_mcp(self, project: Path, cwd: Path) -> dict:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "resolve_context",
                    "arguments": {"task": "root isolation check"},
                },
            },
        ]
        request_bytes = b"".join(
            json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n"
            for request in requests
        )
        result = subprocess.run(
            [sys.executable, str(ENTRY), "mcp", "serve"],
            cwd=cwd,
            env=_environment(project),
            input=request_bytes,
            capture_output=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        responses = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual([response["id"] for response in responses], [1, 2])
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "claude-kit")
        return json.loads(responses[1]["result"]["content"][0]["text"])

    def test_cli_selects_each_project_from_fixed_unrelated_cwd_and_preserves_profile_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alpha = _make_checkout(root, "checkout alpha with spaces", "project_alpha")
            beta = _make_checkout(root, "checkout beta with spaces", "project_beta")
            launch_cwd = root / "unrelated launch cwd"
            launch_cwd.mkdir()

            for project, project_id in ((alpha, "project_alpha"), (beta, "project_beta")):
                with self.subTest(project=project.name):
                    result = self.run_cli("inspect", "--json", cwd=launch_cwd, environment=_environment(project))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["root"], str(project.resolve()))

                    context = self.run_mcp(project, launch_cwd)
                    self.assertEqual(context["manifest"]["project"], project_id)
                    self.assertIn(f"Project: {project_id}", context["context"])

    def test_cli_invalid_project_dir_fails_closed_but_explicit_root_overrides_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = _make_checkout(root, "explicit checkout", "explicit_project")
            launch_cwd = root / "unrelated launch cwd"
            launch_cwd.mkdir()
            invalid_environment = _environment(root / "missing checkout")

            rejected = self.run_cli("inspect", "--json", cwd=launch_cwd, environment=invalid_environment)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("PROJ_DIR", rejected.stderr)
            self.assertEqual(rejected.stdout, "")

            overridden = self.run_cli(
                "inspect",
                "--project-root",
                str(explicit),
                "--json",
                cwd=launch_cwd,
                environment=invalid_environment,
            )
            self.assertEqual(overridden.returncode, 0, overridden.stderr)
            self.assertEqual(json.loads(overridden.stdout)["root"], str(explicit.resolve()))

    def test_cli_unset_project_dir_discovers_root_from_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = _make_checkout(root, "discovered checkout", "discovered_project")
            nested = checkout / "tools" / "runner"
            nested.mkdir(parents=True)
            result = self.run_cli("inspect", "--json", cwd=nested, environment=_environment())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["root"], str(checkout.resolve()))

    def test_cli_project_root_variable_substitution_handles_spaces_and_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = _make_checkout(root, "variable checkout with spaces", "variable_project")
            child = project / "child checkout"
            child.mkdir()
            launch_cwd = root / "unrelated launch cwd"
            launch_cwd.mkdir()
            for token in ("$PROJ_DIR", "${PROJ_DIR}"):
                with self.subTest(token=token):
                    result = self.run_cli(
                        "inspect",
                        "--project-root",
                        f"{token}/child checkout",
                        "--json",
                        cwd=launch_cwd,
                        environment=_environment(project),
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["root"], str(child.resolve()))


if __name__ == "__main__":
    unittest.main()
