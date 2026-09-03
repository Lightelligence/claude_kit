"""The packaged source catalog is not a runtime or EDA success claim."""
import unittest

from claude_kit.upstream import bundled_snapshot, inspect_snapshot


class BundledUpstreamTests(unittest.TestCase):
    def test_bundled_source_integrity_and_existing_server_presence(self):
        snapshot = inspect_snapshot(bundled_snapshot())
        expected = {
            "soc-build", "soc-integrate", "yml2reg", "gen-asic-memmap",
            "gen-memwrap", "excel-yml-gen", "crg-req-to-design", "crg-gen",
            "cr-tree-diag-gen", "soc-openroad",
        }
        servers = snapshot["capabilities"]["servers"]
        self.assertTrue(expected <= servers.keys())
        for name in expected:
            with self.subTest(server=name):
                self.assertEqual(servers[name]["inventory"], "static_python_decorators_not_runtime_schema")
                self.assertEqual(servers[name]["validation"], "not_run")
                self.assertTrue(servers[name]["tools"])

    def test_unsupported_upstream_entries_are_not_mistaken_for_working_tools(self):
        snapshot = inspect_snapshot(bundled_snapshot())
        for name, entry in snapshot["capabilities"]["servers"].items():
            with self.subTest(server=name):
                self.assertNotEqual(entry["validation"], "passed")
                if entry["inventory"] == "missing_script":
                    self.assertEqual(entry["validation"], "unavailable")
                    self.assertEqual(entry["tools"], [])
