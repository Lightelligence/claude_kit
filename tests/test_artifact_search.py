from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claude_kit.artifact_search import search_artifact
from claude_kit.core import KitError, read_artifact


class ArtifactSearchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "sim.log"

    def search(self, payload, queries, **kwargs):
        self.path.write_bytes(payload)
        return search_artifact(self.root, "sim.log", queries, **kwargs)

    def test_hidden_middle_and_end_matches_are_scanned_once(self):
        payload = b"start\n" + b"ordinary\n" * 20_000 + b"FAIL middle\n" + b"ordinary\n" * 20_000 + b"FAIL end"
        result = self.search(payload, ["FAIL", "ordinary", "missing"], max_matches=1, max_output_bytes=12)
        self.assertTrue(result["scan_complete"])
        self.assertEqual([record["count"] for record in result["queries"]], [2, 40_000, 0])
        self.assertTrue(result["matches_truncated"])
        self.assertLessEqual(result["output_bytes"], 12)
        self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(result["file_version"], read_artifact(self.root, "sim.log", 0)["file_version"])
        self.assertNotIn("status", result)
        self.assertNotIn("PASS", json.dumps(result))

    def test_overlaps_duplicates_utf8_and_unterminated_last_line(self):
        payload = "aaaa\n失败失败\nlast失败".encode("utf-8")
        result = self.search(payload, ["aa", "失败", "aa"])
        self.assertEqual([item["count"] for item in result["queries"]], [3, 3, 3])
        hits = [item for item in result["matches"] if item["query_index"] == 1]
        self.assertEqual([item["byte_offset"] for item in hits], [5, 11, 22])
        self.assertEqual([item["line_number"] for item in hits], [2, 2, 3])
        self.assertEqual(self.path.read_bytes(), payload)

    def test_queries_cross_chunk_and_line_boundaries_without_duplicate_hits(self):
        payload = b"x\n" * 8190 + b"abc\ndef" + b"x\n" * 9000
        result = self.search(payload, ["abc\ndef", "def"])
        self.assertEqual([item["count"] for item in result["queries"]], [1, 1])
        hit = next(item for item in result["matches"] if item["query_index"] == 0)
        self.assertEqual(hit["byte_offset"], 16_380)
        self.assertEqual(hit["line_number"], 8191)
        repeated = search_artifact(self.root, "sim.log", ["x\n"], max_matches=0)
        self.assertEqual(repeated["queries"][0]["count"], 17_190)

    def test_empty_and_zero_scan_budget(self):
        result = self.search(b"", ["FAIL"], max_scan_bytes=0)
        self.assertTrue(result["scan_complete"])
        self.assertEqual(result["sha256"], hashlib.sha256(b"").hexdigest())
        result = self.search(b"FAIL", ["FAIL"], max_scan_bytes=0)
        self.assertFalse(result["scan_complete"])
        self.assertEqual(result["bytes_read"], 0)
        self.assertIsNone(result["sha256"])
        self.assertEqual(result["scan_stop_reason"], "scan_byte_limit")

    def test_utf8_query_split_inside_character_at_chunk_boundary(self):
        payload = b"x\n" * 8191 + b"x" + "失败".encode("utf-8") + b"\n"
        result = self.search(payload, ["失败"])
        self.assertTrue(result["scan_complete"])
        self.assertEqual(result["queries"][0]["count"], 1)
        self.assertEqual(result["matches"][0]["byte_offset"], 16_383)
        self.assertEqual(result["matches"][0]["line_number"], 8192)

    def test_long_literal_crosses_chunk_boundary(self):
        query = "start" + "q" * 4088 + "end"
        payload = b"x\n" * 7500 + query.encode() + b"\n"
        result = self.search(payload, [query])
        self.assertTrue(result["scan_complete"])
        self.assertEqual(result["queries"][0]["count"], 1)
        self.assertEqual(result["matches"][0]["byte_offset"], 15_000)
        self.assertTrue(result["matches"][0]["snippet_truncated"])

    def test_scan_limit_partial_counts_and_exact_boundary(self):
        payload = b"FAIL\nFAIL\nFAIL"
        result = self.search(payload, ["FAIL"], max_scan_bytes=7)
        self.assertEqual(result["queries"][0]["count"], 1)
        self.assertEqual(result["bytes_read"], 7)
        self.assertEqual(result["bytes_scanned"], 7)
        self.assertFalse(result["scan_complete"])
        self.assertIsNone(result["sha256"])
        exact = search_artifact(self.root, "sim.log", ["FAIL"], max_scan_bytes=len(payload))
        self.assertTrue(exact["scan_complete"])
        self.assertEqual(exact["queries"][0]["count"], 3)

    def test_high_density_counts_continue_after_preview_limits(self):
        payload = b"aaaa\n" * 30_000
        result = self.search(payload, ["aa", "aaa"], max_matches=3, max_output_bytes=1)
        self.assertEqual([item["count"] for item in result["queries"]], [90_000, 60_000])
        self.assertTrue(result["scan_complete"])
        self.assertEqual(len(result["matches"]), 3)
        self.assertEqual(sum(len(item["text"].encode("utf-8")) for item in result["matches"]), 1)
        self.assertLess(len(json.dumps(result)), 4000)
        no_hits = search_artifact(self.root, "sim.log", ["aa"], max_matches=0)
        self.assertEqual(no_hits["matches"], [])
        self.assertEqual(no_hits["queries"][0]["count"], 90_000)
        self.assertTrue(no_hits["matches_truncated"])

    def test_utf8_replacement_and_budget_account_for_encoded_bytes(self):
        result = self.search(b"\xffFAIL\n" + "失败".encode("utf-8"), ["FAIL", "失败"], max_output_bytes=5)
        self.assertEqual(result["matches"][0]["text_encoding"], "utf-8-replace")
        self.assertIn("\ufffd", result["matches"][0]["text"])
        self.assertLessEqual(sum(len(item["text"].encode("utf-8")) for item in result["matches"]), 5)
        self.assertTrue(result["output_truncated"])
        self.assertTrue(all(item["snippet_truncated"] for item in result["matches"]))
        empty = search_artifact(self.root, "sim.log", ["FAIL"], max_output_bytes=0)
        self.assertEqual(empty["matches"][0]["text"], "")
        self.assertEqual(empty["output_bytes"], 0)

    def test_large_snippets_are_explicitly_truncated(self):
        result = self.search(b"x" * 1000 + b"FAIL" + b"x" * 1000, ["FAIL"])
        self.assertTrue(result["scan_complete"])
        self.assertTrue(result["matches"][0]["snippet_truncated"])
        self.assertLessEqual(result["output_bytes"], 256)
        hit = result["matches"][0]
        self.assertEqual(hit["byte_offset"], 1000)
        self.assertIn("FAIL", hit["text"])

    def test_long_line_stops_with_incomplete_counts_and_no_hash(self):
        result = self.search(b"FAIL\n" + b"x" * 70_000 + b"FAIL\nFAIL", ["FAIL"])
        self.assertFalse(result["scan_complete"])
        self.assertEqual(result["scan_stop_reason"], "line_too_long")
        self.assertEqual(result["bytes_scanned"], 5 + 65_536)
        self.assertEqual(result["queries"][0]["count"], 1)
        self.assertIsNone(result["sha256"])
        exact = self.search(b"x" * 65_536, ["x"], max_matches=0)
        self.assertTrue(exact["scan_complete"])
        self.assertEqual(exact["queries"][0]["count"], 65_536)

    def test_read_requests_are_bounded_including_long_lines(self):
        self.path.write_bytes(b"FAIL\n" + b"x" * 1_000_000)
        original_open = Path.open
        reads = []

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
                if not 0 < size <= 16_384:
                    raise AssertionError(f"unbounded read: {size}")
                reads.append(size)
                return self.stream.read(size)

        def bounded_open(path, *args, **kwargs):
            return GuardedFile(original_open(path, *args, **kwargs))

        with patch.object(Path, "open", bounded_open):
            result = search_artifact(self.root, "sim.log", ["FAIL"], max_scan_bytes=70_000)
        self.assertLessEqual(sum(reads), 70_000)
        self.assertLessEqual(result["bytes_read"], 70_000)
        self.assertEqual(result["scan_stop_reason"], "line_too_long")

    def test_change_during_read_prevents_stable_hash(self):
        self.path.write_bytes(b"FAIL\n" * 5000)
        original_open = Path.open
        artifact = self.path

        class ChangingFile:
            def __init__(self, stream):
                self.stream = stream
                self.changed = False

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def fileno(self):
                return self.stream.fileno()

            def read(self, size):
                data = self.stream.read(size)
                if not self.changed:
                    with original_open(artifact, "ab") as writer:
                        writer.write(b"later\n")
                    self.changed = True
                return data

        with patch.object(Path, "open", lambda path, *args, **kwargs: ChangingFile(original_open(path, *args, **kwargs))):
            result = search_artifact(self.root, "sim.log", ["FAIL"])
        self.assertTrue(result["changed_during_read"])
        self.assertFalse(result["scan_complete"])
        self.assertIsNone(result["sha256"])
        self.assertEqual(result["scan_stop_reason"], "changed_during_read")

    def test_project_boundary_missing_and_nonfile(self):
        self.path.write_bytes(b"FAIL")
        for path in ("../sim.log", str(self.root.parent / "outside.log"), "missing.log", "."):
            with self.subTest(path=path), self.assertRaises(KitError):
                search_artifact(self.root, path, ["FAIL"])

    def test_outward_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            destination = Path(outside) / "secret.log"
            destination.write_bytes(b"FAIL")
            try:
                self.path.symlink_to(destination)
            except OSError as exc:
                self.skipTest(f"Windows symlink privilege unavailable: {exc}")
            with self.assertRaises(KitError):
                search_artifact(self.root, "sim.log", ["FAIL"])

    def test_queries_and_budgets_are_validated_before_read(self):
        for queries in ([], "FAIL", [""], [1], [True], [None], ["x"] * 9, ["x" * 4097], ["失败" * 1000], ["\ud800"]):
            with self.subTest(queries=repr(queries)[:60]), self.assertRaises(KitError):
                search_artifact(self.root, "sim.log", queries)
        for key, ceiling in (("max_output_bytes", 1_000_000), ("max_matches", 1000), ("max_scan_bytes", 1024 ** 3)):
            for value in (True, -1, 1.5, "4", None, ceiling + 1):
                with self.subTest(key=key, value=value), self.assertRaises(KitError):
                    search_artifact(self.root, "sim.log", ["FAIL"], **{key: value})


if __name__ == "__main__":
    unittest.main()
