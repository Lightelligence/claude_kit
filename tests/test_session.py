from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from claude_kit.session import launch_session
from claude_kit.tool_profiles import ToolProfileError


class SessionTests(unittest.TestCase):
    def test_private_subset_cleanup_and_native_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seen = []
            config = {"mcpServers": {"selected": {"command": "test", "env": {"TOKEN": "private"}}}}

            def run(command, **kwargs):
                self.assertEqual(command[:3], ["claude", "--strict-mcp-config", "--mcp-config"])
                path = Path(command[3])
                seen.append(path)
                self.assertEqual(json.loads(path.read_text()), config)
                self.assertEqual(command[4:], ["-p", "Inspect RTL"])
                self.assertEqual(kwargs, {"cwd": root.resolve(), "check": False})
                return type("Result", (), {"returncode": 7})()

            with patch("claude_kit.session.select_tool_profile", return_value=config), patch("claude_kit.session.subprocess.run", side_effect=run):
                self.assertEqual(launch_session(root, "rtl", ["-p", "Inspect RTL"]), 7)
            self.assertFalse(seen[0].exists())

    def test_cannot_override_selected_config(self):
        for argument in ["--mcp-config", "--mcp-config=extra.json", "--strict-mcp-config"]:
            with self.subTest(argument=argument), self.assertRaises(ToolProfileError):
                launch_session(Path.cwd(), "rtl", [argument])

    def test_cleanup_when_native_executable_missing(self):
        seen = []
        def fail(command, **kwargs):
            seen.append(Path(command[3]))
            raise FileNotFoundError("claude")
        with patch("claude_kit.session.select_tool_profile", return_value={"mcpServers": {}}), patch("claude_kit.session.subprocess.run", side_effect=fail):
            with self.assertRaises(FileNotFoundError):
                launch_session(Path.cwd(), "rtl", [])
        self.assertFalse(seen[0].exists())
