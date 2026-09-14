"""Locked adaptations preserve source provenance and refuse silent rebases."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from claude_kit.adaptations import _replacements, bundled_patches, export_adapted
from claude_kit.core import KitError
from claude_kit.upstream import bundled_snapshot, inspect_snapshot


class AdaptationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = bundled_snapshot()
        cls.manifest = inspect_snapshot(cls.snapshot)
        cls.patches = json.loads(bundled_patches().read_text(encoding="utf-8"))

    def test_export_preserves_full_layout_and_pristine_source(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "adapted"
            result = export_adapted(output)
            self.assertEqual(result["status"], "exported_not_activated")
            self.assertEqual(result["functional_validation"], "not_run")
            record = json.loads((output / "adaptation.json").read_text())
            self.assertEqual(set(record["files"]), set(self.manifest["files"]))
            self.assertFalse((output / "manifest.json").exists())
            changed = []
            for name, info in self.manifest["files"].items():
                target = output / "source" / name
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if actual != info["sha256"]:
                    changed.append(name)
                self.assertEqual(actual, record["files"][name]["sha256"])
                if os.name != "nt":
                    self.assertEqual(bool(target.stat().st_mode & 0o111), info["git_mode"] == "100755")
            self.assertEqual(sorted(changed), sorted(item["path"] for item in self.patches["files"]))
            self.assertEqual(inspect_snapshot(self.snapshot), self.manifest)

    def test_changed_commit_base_result_context_and_paths_rejected(self):
        mutations = [
            lambda p: p.update(upstream_commit="0" * 40),
            lambda p: p["files"][0].update(before_sha256="0" * 64),
            lambda p: p["files"][0].update(after_sha256="0" * 64),
            lambda p: p["files"][0]["hunks"][0].update(before=["not present"]),
            lambda p: p["files"][0].update(path="../escape.py"),
            lambda p: p["files"].append(p["files"][0]),
            lambda p: p["files"][0]["hunks"][0].update(after=["tampered"]),
        ]
        for mutate in mutations:
            candidate = copy.deepcopy(self.patches)
            mutate(candidate)
            with self.subTest(mutation=mutations.index(mutate)), self.assertRaises(KitError):
                _replacements(self.snapshot, self.manifest, candidate)

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            sentinel = output / "keep.txt"
            sentinel.write_text("user data")
            with self.assertRaisesRegex(KitError, "new directory"):
                export_adapted(output)
            self.assertEqual(sentinel.read_text(), "user data")
            self.assertEqual(list(output.iterdir()), [sentinel])

    def test_output_inside_snapshot_rejected_before_writing(self):
        output = self.snapshot / "must-not-be-created"
        with self.assertRaisesRegex(KitError, "outside the pristine"):
            export_adapted(output)
        self.assertFalse(output.exists())

    def test_invalid_patch_creates_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "invalid.json"
            candidate.write_text('{"schema_version": 1, "upstream_commit": "wrong"}')
            with patch("claude_kit.adaptations.bundled_patches", return_value=candidate):
                with self.assertRaises(KitError):
                    export_adapted(root / "output")
            self.assertFalse((root / "output").exists())

    def test_link_destination_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            link = root / "link"
            target = root / "target"
            target.mkdir()
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("Creating symlinks is unavailable")
            with self.assertRaises(KitError):
                export_adapted(link / "output")
            self.assertEqual(list(target.iterdir()), [])
