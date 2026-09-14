"""Launch native Claude with an explicit, temporary MCP server subset."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

from .tool_profiles import ToolProfileError, select_tool_profile


def launch_session(root: Path, profile: str, arguments: list[str]) -> int:
    # A second config flag could silently widen the selected tool surface.
    forbidden = {"--mcp-config", "--strict-mcp-config"}
    if any(arg.split("=", 1)[0] in forbidden for arg in arguments):
        raise ToolProfileError("Session owns --mcp-config and --strict-mcp-config")
    root = root.resolve()
    config = select_tool_profile(root, profile)
    # No model, permission or project settings overrides. The file is private on
    # POSIX and removed after the native process exits, including on exceptions.
    with tempfile.TemporaryDirectory(prefix="claude-kit-session-") as directory:
        path = Path(directory) / "mcp.json"
        with path.open("x", encoding="utf-8") as stream:
            if os.name != "nt":
                os.chmod(path, 0o600)
            json.dump(config, stream)
        return subprocess.run(
            ["claude", "--strict-mcp-config", "--mcp-config", str(path), *arguments],
            cwd=root,
            check=False,
        ).returncode
