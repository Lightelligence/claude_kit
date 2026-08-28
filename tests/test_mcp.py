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


def newline_frame(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8") + b"\n"


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


def read_newline_frames(payload: bytes) -> list[dict]:
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


class McpTests(unittest.TestCase):
    def test_newline_stdio_bridge_lists_tools(self) -> None:
        process = subprocess.Popen(
            [sys.executable, str(ENTRY), "mcp", "serve", "--project-root", str(FIXTURE)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        request = b"".join(
            [
                newline_frame({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                }),
                newline_frame({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
                newline_frame({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            ]
        )
        try:
            stdout, stderr = process.communicate(input=request, timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            self.fail(f"newline MCP bridge timed out; stderr={stderr.decode(errors='replace')}")
        self.assertEqual(process.returncode, 0, stderr.decode(errors="replace"))
        responses = read_newline_frames(stdout)
        self.assertEqual([response["id"] for response in responses], [1, 2])
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "claude-kit")
        self.assertIn("plan_task", {tool["name"] for tool in responses[1]["result"]["tools"]})

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
            self.assertIn("read_artifact", names)
            self.assertIn("discover_regression_artifacts", names)
            self.assertIn("read_regression_artifact", names)
            self.assertIn("list_skills", names)
            self.assertIn("list_providers", names)
            self.assertNotIn("run_check", names)
            evidence_tool = next(tool for tool in tools if tool["name"] == "review_evidence")
            self.assertIn("strict", evidence_tool["inputSchema"]["properties"])
            self.assertIn("list_workflows", names)
            self.assertIn("plan_task", names)
            self.assertIn("list_checks", names)

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": "list_providers", "arguments": {}},
            }))
            process.stdin.flush()
            providers_response = read_frame(process.stdout)
            providers = json.loads(providers_response["result"]["content"][0]["text"])
            self.assertEqual(providers[0]["id"], "xverif")

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

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "read_artifact", "arguments": {"path": "out/logs/README.md", "max_bytes": 4}},
            }))
            process.stdin.flush()
            artifact = read_frame(process.stdout)
            artifact_text = artifact["result"]["content"][0]["text"]
            artifact_payload = json.loads(artifact_text)
            self.assertTrue(artifact_payload["truncated"])

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "plan_task",
                    "arguments": {"workflow": "debug", "task": "debug APB timeout in simulation"},
                },
            }))
            process.stdin.flush()
            plan_response = read_frame(process.stdout)
            plan = json.loads(plan_response["result"]["content"][0]["text"])
            self.assertEqual(plan["workflow"]["id"], "debug")
            self.assertIn("debugger", plan["roles"])

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "list_checks", "arguments": {}},
            }))
            process.stdin.flush()
            checks_response = read_frame(process.stdout)
            checks = json.loads(checks_response["result"]["content"][0]["text"])
            self.assertTrue(any(item["name"] == "inspect" for item in checks))

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "resolve_context",
                    "arguments": {
                        "roles": ["reviewer"],
                        "packs": ["common"],
                        "skills": ["rtl-dv-context"],
                        "task": "review APB",
                    },
                },
            }))
            process.stdin.flush()
            context_response = read_frame(process.stdout)
            context_text = json.loads(context_response["result"]["content"][0]["text"])["context"]
            self.assertIn("RTL/DV Context", context_text)
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
            self.assertIn("run_checks", {tool["name"] for tool in tools})

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

            process.stdin.write(frame({
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "run_checks",
                    "arguments": {"names": ["inspect", "confirmed"], "confirm": True},
                },
            }))
            process.stdin.flush()
            batch = read_frame(process.stdout)
            batch_payload = json.loads(batch["result"]["content"][0]["text"])
            self.assertEqual(batch_payload["summary"]["passed"], 2)
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
