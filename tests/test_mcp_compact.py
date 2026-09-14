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


class CompactMcpTests(unittest.TestCase):
    def _start(self, *options: str) -> subprocess.Popen:
        return subprocess.Popen(
            [
                sys.executable,
                str(ENTRY),
                "mcp",
                "serve",
                "--project-root",
                str(FIXTURE),
                *options,
            ],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _stop(self, process: subprocess.Popen) -> None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def _request(self, process: subprocess.Popen, request_id: int, method: str, params: dict | None = None) -> dict:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(frame({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }))
        process.stdin.flush()
        return read_frame(process.stdout)

    def _initialize(self, process: subprocess.Popen) -> None:
        response = self._request(process, 1, "initialize")
        self.assertEqual(response["result"]["serverInfo"]["name"], "claude-kit")

    def _tools(self, process: subprocess.Popen) -> list[dict]:
        return self._request(process, 2, "tools/list")["result"]["tools"]

    @staticmethod
    def _payload(response: dict) -> object:
        return json.loads(response["result"]["content"][0]["text"])

    @staticmethod
    def _schema_bytes(tools: list[dict]) -> int:
        return len(json.dumps(tools, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def test_compact9_and_default_full14_readonly_schema(self) -> None:
        full = self._start()
        try:
            self._initialize(full)
            full_tools = self._tools(full)
        finally:
            self._stop(full)

        compact = self._start("--tool-profile", "compact")
        try:
            self._initialize(compact)
            compact_tools = self._tools(compact)
        finally:
            self._stop(compact)

        full_names = {tool["name"] for tool in full_tools}
        compact_names = {tool["name"] for tool in compact_tools}
        catalog_names = {
            "list_roles",
            "list_packs",
            "list_providers",
            "list_skills",
            "list_workflows",
            "list_checks",
        }
        self.assertEqual(len(full_tools), 14)
        self.assertEqual(len(compact_tools), 9)
        self.assertTrue(catalog_names.issubset(full_names))
        self.assertTrue(catalog_names.isdisjoint(compact_names))
        self.assertIn("list_catalog", compact_names)
        self.assertNotIn("run_check", full_names | compact_names)
        self.assertLess(self._schema_bytes(compact_tools), self._schema_bytes(full_tools))

        list_catalog = next(tool for tool in compact_tools if tool["name"] == "list_catalog")
        schema = list_catalog["inputSchema"]
        self.assertEqual(schema["required"], ["category"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["category"]["enum"],
            ["roles", "packs", "providers", "skills", "workflows", "checks"],
        )

    def test_six_compact_catalogs_match_historical_calls(self) -> None:
        process = self._start("--tool-profile", "compact")
        try:
            self._initialize(process)
            for request_id, (category, historical_name) in enumerate(
                (
                    ("roles", "list_roles"),
                    ("packs", "list_packs"),
                    ("providers", "list_providers"),
                    ("skills", "list_skills"),
                    ("workflows", "list_workflows"),
                    ("checks", "list_checks"),
                ),
                start=10,
            ):
                historical = self._request(
                    process,
                    request_id,
                    "tools/call",
                    {"name": historical_name, "arguments": {}},
                )
                compact = self._request(
                    process,
                    request_id + 100,
                    "tools/call",
                    {"name": "list_catalog", "arguments": {"category": category}},
                )
                self.assertEqual(self._payload(compact), self._payload(historical), category)
        finally:
            self._stop(process)

    def test_list_catalog_validates_required_type_enum_and_unknown_arguments(self) -> None:
        process = self._start("--tool-profile", "compact")
        try:
            self._initialize(process)
            cases = (
                (10, {}, "list_catalog requires category"),
                (11, {"category": 3}, "list_catalog category must be a string"),
                (12, {"category": "unknown"}, "list_catalog category must be one of"),
                (13, {"category": "roles", "extra": True}, "list_catalog unknown argument: extra"),
            )
            for request_id, arguments, message in cases:
                response = self._request(
                    process,
                    request_id,
                    "tools/call",
                    {"name": "list_catalog", "arguments": arguments},
                )
                self.assertIn(message, response["error"]["message"])
        finally:
            self._stop(process)

    def test_compact_readonly_denies_each_execution_operation(self) -> None:
        process = self._start("--tool-profile", "compact")
        try:
            self._initialize(process)
            names = {tool["name"] for tool in self._tools(process)}
            self.assertNotIn("run_check", names)
            self.assertNotIn("run_checks", names)
            for request_id, name, arguments in (
                (10, "run_check", {"name": "inspect", "confirm": True}),
                (11, "run_checks", {"names": ["inspect"], "confirm": True}),
            ):
                response = self._request(
                    process,
                    request_id,
                    "tools/call",
                    {"name": name, "arguments": arguments},
                )
                self.assertIn(f"{name} is disabled", response["error"]["message"])
        finally:
            self._stop(process)


if __name__ == "__main__":
    unittest.main()
