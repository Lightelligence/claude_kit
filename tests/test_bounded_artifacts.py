from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from claude_kit.core import read_artifact, read_regression_artifact


class BoundedArtifactTests(unittest.TestCase):
    def test_large_logs_never_read_more_than_requested_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "sim.log"
            # File size is larger than the maximum allowed response, as in DV logs.
            log.write_bytes(b"FAIL" + b"x" * 2_000_000)
            profile = {"artifacts": {"regression": {"root": str(root)}}}
            original_open = Path.open
            for limit in (0, 4, 128):
                for reader in (lambda: read_artifact(root, "sim.log", limit),
                               lambda: read_regression_artifact(profile, "sim.log", limit)):
                    with self.subTest(limit=limit, reader=reader):
                        reads = []
                        test = self

                        class GuardedFile:
                            def __init__(self, stream):
                                self.stream = stream

                            def __enter__(self):
                                return self

                            def __exit__(self, *args):
                                self.stream.close()

                            def fileno(self):
                                return self.stream.fileno()

                            def read(self, size=-1):
                                test.assertGreaterEqual(size, 0, "unbounded log read")
                                test.assertLessEqual(size, limit)
                                reads.append(size)
                                return self.stream.read(size)

                        def bounded_open(path, *args, **kwargs):
                            return GuardedFile(original_open(path, *args, **kwargs))

                        with patch.object(Path, "open", bounded_open):
                            result = reader()
                        self.assertEqual(result["bytes"], 2_000_004)
                        self.assertTrue(result["truncated"])
                        self.assertEqual(len(result["text"]), limit)
                        self.assertLessEqual(sum(reads), limit)

    def test_empty_exact_boundary_and_utf8_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "sim.log"
            profile = {"artifacts": {"regression": {"root": str(root)}}}
            for payload in (b"", b"done", "完成\n".encode("utf-8")):
                log.write_bytes(payload)
                for budget in (0, 1, len(payload), len(payload) + 10):
                    local = read_artifact(root, "sim.log", budget)
                    external = read_regression_artifact(profile, "sim.log", budget)
                    for result in (local, external):
                        self.assertEqual(result["bytes"], len(payload))
                        self.assertEqual(result["truncated"], len(payload) > budget)
                        self.assertEqual(result["text"], payload[:budget].decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
