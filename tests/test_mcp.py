from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_project"
ENTRY = ROOT / "bin" / "claude-kit"


def frame(value: dict) -> bytes:
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload


def read_frame(stream) -> dict:
    headers = {}
    while True:
        line = stream.readline()
        if line in (b"\n", b"\r\n"):
            break
        key, value = line.decode("ascii").split(":", 1)
        headers[key.lower()] = value.strip()
    payload = stream.read(int(headers["content-length"]))
    return json.loads(payload.decode("utf-8"))


class McpTests(unittest.TestCase):
    def test_read_only_bridge_lists_tools_and_resolves_context(self) -> None:
        process = subprocess.Popen(
            [sys.executable, str(ENTRY), "mcp", "serve", "--project-root", str(FIXTURE)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        try:
            process.stdin.write(frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
            process.stdin.flush()
            initialized = read_frame(process.stdout)
            self.assertEqual(initialized["result"]["serverInfo"]["name"], "claude-kit")

            process.stdin.write(frame({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}))
            process.stdin.flush()
            tools = read_frame(process.stdout)["result"]["tools"]
            names = {tool["name"] for tool in tools}
            self.assertIn("resolve_context", names)
            self.assertNotIn("run_check", names)
            evidence_tool = next(tool for tool in tools if tool["name"] == "review_evidence")
            self.assertIn("strict", evidence_tool["inputSchema"]["properties"])

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_project_profile", "arguments": {}},
            }))
            process.stdin.flush()
            response = read_frame(process.stdout)
            text = response["result"]["content"][0]["text"]
            self.assertNotIn("fixture-secret", text)
            self.assertIn("minimal_fixture", text)
        finally:
            process.terminate()
            process.wait(timeout=5)
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

    def test_exec_bridge_requires_confirmation(self) -> None:
        process = subprocess.Popen(
            [sys.executable, str(ENTRY), "mcp", "serve", "--project-root", str(FIXTURE), "--allow-exec"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        try:
            process.stdin.write(frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
            process.stdin.flush()
            read_frame(process.stdout)

            process.stdin.write(frame({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}))
            process.stdin.flush()
            tools = read_frame(process.stdout)["result"]["tools"]
            self.assertIn("run_check", {tool["name"] for tool in tools})

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "run_check", "arguments": {"name": "inspect", "confirm": False}},
            }))
            process.stdin.flush()
            denied = read_frame(process.stdout)
            self.assertIn("confirm=true", denied["error"]["message"])

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "run_check", "arguments": {"name": "inspect", "confirm": True}},
            }))
            process.stdin.flush()
            allowed = read_frame(process.stdout)
            self.assertIn('"status": "passed"', allowed["result"]["content"][0]["text"])
        finally:
            process.terminate()
            process.wait(timeout=5)
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()


if __name__ == "__main__":
    unittest.main()
