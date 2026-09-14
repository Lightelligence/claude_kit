from __future__ import annotations

import copy
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claude_kit.tool_profiles import (
    ToolProfileError,
    profile_catalog,
    select_tool_profile,
)


class ToolProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "project"
        (self.root / ".claude").mkdir(parents=True)
        self.mcp_config: dict[str, Any] = {
            "mcpServers": {
                "rtl-tools": {
                    "type": "stdio",
                    "command": "python",
                    "args": [r"C:\licensed\rtl-tools\server.py", "--mode", "read"],
                    "env": {"TOKEN": "secret-token", "MODE": "readonly"},
                    "transport": {"kind": "stdio", "metadata": {"timeout_ms": 1500}},
                    "custom_metadata": {"nested": [1, False, None, {"keep": "exact"}]},
                },
                "wave-tools": {
                    "type": "http",
                    "url": "https://example.invalid/mcp",
                    "headers": {"Authorization": "Bearer secret-header"},
                    "transport": {"retry": {"count": 2}},
                },
                "unused-tools": {"command": "project-owned-server"},
            }
        }
        self.profile_config: dict[str, Any] = {
            "schema_version": 1,
            "profiles": {
                "rtl": {"description": "RTL inspection tools", "servers": ["rtl-tools"]},
                "debug": {
                    "description": "RTL and waveform tools",
                    "servers": ["rtl-tools", "wave-tools"],
                },
            },
        }
        self._write(self.mcp_config, self.profile_config)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_explicit_catalog_keeps_optional_servers_outside_default_config(self):
        catalog=self.root/'.claude/mcp-catalog.json'
        catalog.write_text(json.dumps(self.mcp_config),encoding='utf-8')
        self.profile_config['mcp_config']='.claude/mcp-catalog.json'
        self._write({'mcpServers':{'rtl-tools':self.mcp_config['mcpServers']['rtl-tools']}},self.profile_config)
        selected=select_tool_profile(self.root,'debug')
        self.assertIn('wave-tools',selected['mcpServers'])
        self.assertNotIn('wave-tools',json.loads((self.root/'.mcp.json').read_text())['mcpServers'])

    def test_catalog_path_cannot_escape_project(self):
        for filename in ('../outside.json',str(self.root/'.mcp.json')):
            self.profile_config['mcp_config']=filename
            self._write(self.mcp_config,self.profile_config)
            with self.assertRaises(ToolProfileError): select_tool_profile(self.root,'rtl')

    def test_cli_catalog_does_not_expose_server_secrets(self) -> None:
        from claude_kit.cli import main

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["tool-profiles", "--project-root", str(self.root)])
        self.assertEqual(status, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["profiles"], profile_catalog(self.root))
        self.assertNotIn("secret-token", output.getvalue())
        self.assertNotIn("secret-header", output.getvalue())

    def _write(self, mcp_config: Any, profile_config: Any) -> None:
        (self.root / ".mcp.json").write_text(
            json.dumps(mcp_config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (self.root / ".claude/tool-profiles.json").write_text(
            json.dumps(profile_config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def test_selection_preserves_opaque_server_values_and_files(self) -> None:
        mcp_path = self.root / ".mcp.json"
        profile_path = self.root / ".claude/tool-profiles.json"
        mcp_before = mcp_path.read_bytes()
        profile_before = profile_path.read_bytes()

        selected = select_tool_profile(self.root, "debug")

        self.assertEqual(
            selected,
            {
                "mcpServers": {
                    "rtl-tools": self.mcp_config["mcpServers"]["rtl-tools"],
                    "wave-tools": self.mcp_config["mcpServers"]["wave-tools"],
                }
            },
        )
        self.assertEqual(
            selected["mcpServers"]["rtl-tools"]["args"],
            [r"C:\licensed\rtl-tools\server.py", "--mode", "read"],
        )
        self.assertEqual(
            selected["mcpServers"]["rtl-tools"]["env"],
            {"TOKEN": "secret-token", "MODE": "readonly"},
        )
        self.assertEqual(
            selected["mcpServers"]["rtl-tools"]["transport"],
            {"kind": "stdio", "metadata": {"timeout_ms": 1500}},
        )
        self.assertEqual(mcp_path.read_bytes(), mcp_before)
        self.assertEqual(profile_path.read_bytes(), profile_before)

    def test_catalog_returns_only_profile_metadata_without_credentials(self) -> None:
        catalog = profile_catalog(self.root)

        self.assertEqual(
            catalog,
            [
                {"name": "rtl", "description": "RTL inspection tools", "servers": ["rtl-tools"]},
                {
                    "name": "debug",
                    "description": "RTL and waveform tools",
                    "servers": ["rtl-tools", "wave-tools"],
                },
            ],
        )
        catalog_text = json.dumps(catalog, ensure_ascii=False)
        self.assertNotIn("secret-token", catalog_text)
        self.assertNotIn("secret-header", catalog_text)
        self.assertNotIn("Authorization", catalog_text)
        self.assertNotIn("licensed\\rtl-tools", catalog_text)

    def test_selection_requires_an_explicit_known_profile_name(self) -> None:
        for name in (None, 3, "", "   ", "missing", " rtl"):
            with self.subTest(name=name):
                with self.assertRaises(ToolProfileError):
                    select_tool_profile(self.root, name)  # type: ignore[arg-type]

    def test_unknown_server_reference_is_rejected(self) -> None:
        profile_config = copy.deepcopy(self.profile_config)
        profile_config["profiles"]["bad"] = {
            "description": "References a server not in .mcp.json",
            "servers": ["missing-tools"],
        }
        self._write(self.mcp_config, profile_config)

        with self.assertRaises(ToolProfileError):
            select_tool_profile(self.root, "bad")
        with self.assertRaises(ToolProfileError):
            profile_catalog(self.root)

    def test_profile_server_lists_must_be_nonempty_and_unique(self) -> None:
        for servers in ([], ["rtl-tools", "rtl-tools"], [""]):
            with self.subTest(servers=servers):
                profile_config = copy.deepcopy(self.profile_config)
                profile_config["profiles"]["bad"] = {
                    "description": "Malformed server selection",
                    "servers": servers,
                }
                self._write(self.mcp_config, profile_config)
                with self.assertRaises(ToolProfileError):
                    profile_catalog(self.root)

    def test_malformed_and_unknown_envelope_fields_are_rejected(self) -> None:
        cases = (
            ([], self.profile_config),
            (self.mcp_config, {"schema_version": 2, "profiles": self.profile_config["profiles"]}),
            (self.mcp_config, {"schema_version": 1}),
            (
                self.mcp_config,
                {"schema_version": 1, "profiles": self.profile_config["profiles"], "extra": True},
            ),
            (
                self.mcp_config,
                {
                    "schema_version": 1,
                    "profiles": {
                        "rtl": {
                            "description": "RTL inspection tools",
                            "servers": ["rtl-tools"],
                            "enabled": True,
                        }
                    },
                },
            ),
            (
                self.mcp_config,
                {"schema_version": 1, "profiles": {"rtl": []}},
            ),
            (
                self.mcp_config,
                {
                    "schema_version": 1,
                    "profiles": {
                        "rtl": {"description": 7, "servers": ["rtl-tools"]}
                    },
                },
            ),
            (
                self.mcp_config,
                {
                    "schema_version": 1,
                    "profiles": {
                        "rtl": {"description": "RTL inspection tools", "servers": "rtl-tools"}
                    },
                },
            ),
            ({"mcpServers": [], "other": "must not be dropped"}, self.profile_config),
            ({"other": "must not be dropped"}, self.profile_config),
            (
                {"mcpServers": {"rtl-tools": ["not an object"]}},
                self.profile_config,
            ),
        )
        for mcp_config, profile_config in cases:
            with self.subTest(mcp_config=mcp_config, profile_config=profile_config):
                self._write(mcp_config, profile_config)
                with self.assertRaises(ToolProfileError):
                    profile_catalog(self.root)

    def test_duplicate_json_object_fields_are_rejected(self) -> None:
        (self.root / ".mcp.json").write_text(
            '{"mcpServers":{"rtl-tools":{"command":"one"},"rtl-tools":{"command":"two"}}}',
            encoding="utf-8",
        )
        with self.assertRaises(ToolProfileError):
            profile_catalog(self.root)

    def test_profile_and_root_paths_are_resolved_safely(self) -> None:
        with self.assertRaises(ToolProfileError):
            profile_catalog(self.root / "missing")
        root_file = self.root / "root-file"
        root_file.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(ToolProfileError):
            profile_catalog(root_file)

    def test_profile_symlink_outside_project_is_rejected(self) -> None:
        outside = Path(self.tempdir.name) / "outside-tool-profiles.json"
        outside.write_text(
            json.dumps(self.profile_config),
            encoding="utf-8",
        )
        profile_path = self.root / ".claude/tool-profiles.json"
        profile_path.unlink()
        try:
            if os.name == "nt":
                profile_path.symlink_to(outside, target_is_directory=False)
            else:
                profile_path.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        with self.assertRaises(ToolProfileError):
            profile_catalog(self.root)


if __name__ == "__main__":
    unittest.main()
