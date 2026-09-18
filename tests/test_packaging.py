from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = ROOT / "src" / "claude_kit" / "resources"


def extract_regular_archive(archive: tarfile.TarFile, destination: Path) -> None:
    """Extract a build-produced sdist without relying on newer tar filters."""
    root = destination.resolve()
    for member in archive.getmembers():
        relative = PurePosixPath(member.name)
        if relative.is_absolute() or ".." in relative.parts:
            raise AssertionError(f"unsafe sdist member: {member.name}")
        target = destination.joinpath(*relative.parts)
        if not target.resolve().is_relative_to(root):
            raise AssertionError(f"sdist member escapes extraction root: {member.name}")
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not member.isfile():
            raise AssertionError(f"unsupported sdist member type: {member.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        stream = archive.extractfile(member)
        if stream is None:
            raise AssertionError(f"cannot read sdist member: {member.name}")
        with stream, target.open("wb") as output:
            shutil.copyfileobj(stream, output)
        if os.name != "nt":
            target.chmod(member.mode & 0o777)


BUILD_PROBE = r"""
import sys
from pathlib import Path

from setuptools.build_meta import build_sdist, build_wheel

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
print(build_wheel(str(output)))
print(build_sdist(str(output)))
"""

INSTALLED_PROBE = r"""
import importlib.metadata
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

import claude_kit
from claude_kit.core import evidence_template, resource_root, role_catalog, skill_catalog
from claude_kit.upstream import bundled_snapshot

resources = resource_root()
snapshot_root = bundled_snapshot()
snapshot = json.loads((snapshot_root / "manifest.json").read_text(encoding="utf-8"))
files = sorted(
    path.relative_to(resources).as_posix()
    for path in resources.rglob("*")
    if path.is_file()
)
print(json.dumps({
    "distribution_version": importlib.metadata.version("claude-kit"),
    "module_version": claude_kit.__version__,
    "module_file": str(Path(claude_kit.__file__).resolve()),
    "resource_files": files,
    "role_count": len(role_catalog()),
    "skill_count": len(skill_catalog()),
    "evidence_template": json.loads(evidence_template())["schema_version"],
    "snapshot_commit": snapshot["commit"],
    "snapshot_source_files": sorted(
        path.relative_to(resources).as_posix()
        for path in (snapshot_root / "source").rglob("*")
        if path.is_file()
    ),
}))
"""


class InstalledDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary_directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._temporary_directory.cleanup)
        cls.temporary_root = Path(cls._temporary_directory.name)
        cls.build_source = cls.temporary_root / "source"
        cls.dist_directory = cls.temporary_root / "dist"
        shutil.copytree(
            ROOT,
            cls.build_source,
            ignore=shutil.ignore_patterns(".git", "build", "dist", "__pycache__", "*.pyc", "*.pyo"),
        )

        result = subprocess.run(
            [sys.executable, "-c", BUILD_PROBE, str(cls.dist_directory)],
            cwd=cls.build_source,
            env=cls._clean_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(f"distribution build failed:\n{result.stdout}\n{result.stderr}")

        wheels = list(cls.dist_directory.glob("*.whl"))
        sdists = list(cls.dist_directory.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise AssertionError(f"expected one wheel and one sdist, found {wheels!r} and {sdists!r}")
        cls.wheel = wheels[0]
        cls.sdist = sdists[0]

        with (ROOT / "pyproject.toml").open("rb") as stream:
            cls.expected_version = tomllib.load(stream)["project"]["version"]
        cls.expected_resources = sorted(
            path.relative_to(RESOURCE_ROOT).as_posix()
            for path in RESOURCE_ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        )

    @classmethod
    def _clean_environment(cls) -> dict[str, str]:
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["TMPDIR"] = str(cls.temporary_root)
        return environment

    def _install_wheel_and_probe(self, artifact: Path, name: str) -> dict[str, object]:
        install_root = self.temporary_root / name
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--ignore-installed",
                "--no-compile",
                "--no-deps",
                "--target",
                str(install_root),
                str(artifact),
            ],
            cwd=self.temporary_root,
            env=self._clean_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(install.returncode, 0, f"wheel install failed:\n{install.stdout}\n{install.stderr}")

        probe = subprocess.run(
            [sys.executable, "-c", INSTALLED_PROBE, str(install_root)],
            cwd=self.temporary_root,
            env=self._clean_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, f"installed-package probe failed:\n{probe.stdout}\n{probe.stderr}")
        payload = json.loads(probe.stdout)
        self.assertTrue(Path(payload["module_file"]).is_relative_to(install_root.resolve()))
        return payload

    def _assert_installed_payload(self, payload: dict[str, object]) -> None:
        self.assertEqual(payload["distribution_version"], self.expected_version)
        self.assertEqual(payload["module_version"], self.expected_version)
        self.assertEqual(payload["resource_files"], self.expected_resources)
        self.assertGreater(payload["role_count"], 0)
        self.assertGreater(payload["skill_count"], 0)
        self.assertEqual(payload["evidence_template"], 1)
        self.assertRegex(payload["snapshot_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(
            payload["snapshot_source_files"],
            [name for name in self.expected_resources if name.startswith("upstream/vibe_soc/source/")],
        )

    def test_installed_wheel_resources_and_version(self) -> None:
        payload = self._install_wheel_and_probe(self.wheel, "wheel-install")
        self._assert_installed_payload(payload)

    def test_installed_sdist_resources_and_version(self) -> None:
        extraction_root = self.temporary_root / "sdist-extraction"
        extraction_root.mkdir()
        with tarfile.open(self.sdist, mode="r:gz") as archive:
            extract_regular_archive(archive, extraction_root)
        source_root = next(extraction_root.iterdir())
        rebuilt_directory = self.temporary_root / "sdist-rebuilt"
        rebuilt_directory.mkdir()
        build = subprocess.run(
            [sys.executable, "-c", BUILD_PROBE.split("print(build_sdist", 1)[0], str(rebuilt_directory)],
            cwd=source_root,
            env=self._clean_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(build.returncode, 0, f"sdist wheel build failed:\n{build.stdout}\n{build.stderr}")
        rebuilt_wheel = next(rebuilt_directory.glob("*.whl"))
        payload = self._install_wheel_and_probe(rebuilt_wheel, "sdist-install")
        self._assert_installed_payload(payload)


if __name__ == "__main__":
    unittest.main()
