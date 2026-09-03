import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from claude_kit.core import KitError
from claude_kit.upstream import _run_git_process, _stage_from_repo


class UpstreamProcessTests(unittest.TestCase):
    def test_tree_scan_does_not_fetch_excluded_blob_sizes(self):
        def git(repo, *args):
            if args[0] == "rev-parse":
                return "a" * 40
            self.assertEqual(args[0], "ls-tree")
            self.assertNotIn("-l", args)
            return "100644 blob " + "b" * 40 + "\tchip/huge.v\0"
        with patch("claude_kit.upstream._git", side_effect=git):
            with self.assertRaisesRegex(KitError, "Empty"):
                _stage_from_repo(Path("unused"), "main", Path("unused-output"))

    def test_timeout_bounds_descendants_holding_output_pipes(self):
        child = "import time; time.sleep(3)"
        parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(20)"
        started = time.monotonic()
        with self.assertRaises((KitError, subprocess.TimeoutExpired)):
            _run_git_process([sys.executable, "-c", parent], timeout=0.3)
        self.assertLess(time.monotonic() - started, 2.5)
