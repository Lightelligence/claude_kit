"""License-free regression checks for the relocated Claude Code contract.

Parse real examples/configuration; never invoke a model, MCP operation or EDA.
"""
import ast
import argparse
import contextlib
import io
import json
import re
import shlex
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]


class ClaudeContractTests(unittest.TestCase):
    def test_pipeline_update_examples_parse_real_cli(self):
        # Execute the real parser body without importing the Linux-only state
        # locking code or allowing state writes. This check also runs on Windows.
        path = SCRIPTS / "loop_state_core.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nodes = [node for node in tree.body if
                 (isinstance(node, ast.FunctionDef) and node.name == "update_main") or
                 (isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id == "STAGE_ORDER"
                     for target in node.targets))]
        namespace = {"argparse": argparse, "update_state": mock.Mock(return_value="unused")}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        document = (ROOT / ".claude/rules/25_pipeline_state_bazel.md").read_text(encoding="utf-8")
        commands = re.findall(
            r"python3 \.claude/scripts/update_state\.py (.*?)(?=\n\n|\n```)",
            document.replace("\\\n", " "), re.S,
        )
        self.assertEqual(len(commands), 3)
        for command in commands:
            argv = ["update_state.py", *shlex.split(command)]
            update = namespace["update_state"]
            update.reset_mock()
            with self.subTest(argv=argv), mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(namespace["update_main"](), 0)
                update.assert_called_once()
                if "verif" in argv:
                    self.assertTrue(update.call_args.kwargs["run_id"])
                    self.assertTrue(update.call_args.kwargs["source_fingerprint"])

    def test_bazel_tool_references_exist(self):
        source = (ROOT / ".claude/skills/soc-build-bazel/mcp_server.py").read_text(encoding="utf-8")
        tools = {node.name for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.FunctionDef) and any(
                     isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                     and d.func.attr == "tool" for d in node.decorator_list)}
        references = set()
        for directory in ["rules", "agents"]:
            for path in (ROOT / ".claude" / directory).glob("*.md"):
                references.update(re.findall(r"soc-build-bazel\.([a-z_]+)", path.read_text(encoding="utf-8")))
        self.assertTrue(references)
        self.assertFalse(references - tools, references - tools)

    def test_tool_examples_match_function_parameters(self):
        source = (ROOT / ".claude/skills/soc-build-bazel/mcp_server.py").read_text(encoding="utf-8")
        functions = {node.name: node for node in ast.walk(ast.parse(source))
                     if isinstance(node, ast.FunctionDef)}
        document = (ROOT / ".claude/rules/22_toolchain_bazel.md").read_text(encoding="utf-8")
        examples = re.findall(r"`soc-build-bazel\.(\w+)`[^\n]*\n```json\n(.*?)\n```", document, re.S)
        self.assertEqual(len(examples), 5)
        for name, payload in examples:
            args = json.loads(payload)
            function = functions[name]
            parameters = [arg.arg for arg in function.args.args]
            required = parameters[:len(parameters) - len(function.args.defaults)]
            self.assertFalse(set(args) - set(parameters))
            self.assertFalse(set(required) - set(args))

    def test_execution_agents_allow_registered_mcp_and_skills(self):
        servers = json.loads((ROOT / ".claude/mcp-catalog.json").read_text(encoding="utf-8"))["mcpServers"]
        for role in ["rtl-designer", "verification-engineer", "integrator", "synthesis-engineer"]:
            path = ROOT / f".claude/agents/soc-{role}.md"
            text = path.read_text(encoding="utf-8")
            frontmatter = text.split("---", 2)[1]
            allowed = re.findall(r"^  - (\S+)$", frontmatter, re.M)
            with self.subTest(role=role):
                self.assertIn("Skill", allowed)
                self.assertIn("mcp__soc-build-bazel__*", allowed)
                self.assertIn("mcp__claude-kit__*", allowed)
                if role == "integrator":
                    self.assertIn("mcp__soc-integrate-bazel__*", allowed)
                for entry in allowed:
                    if entry.startswith("mcp__"):
                        self.assertIn(entry.split("__")[1], servers)
                self.assertIn("DV check menu", text)
                self.assertIn(".claude/CLAUDE.md", text)

    def test_global_execution_rules_reference_authoritative_menu(self):
        for name in ["00_loop_modes", "01_swarm_flow", "02_toolchain",
                     "11_verif_recovery_gate", "12_syn_pd_gate",
                     "21_swarm_flow_bazel", "22_toolchain_bazel"]:
            text = (ROOT / f".claude/rules/{name}.md").read_text(encoding="utf-8")
            with self.subTest(rule=name):
                self.assertIn("DV check menu", text)
                self.assertIn(".claude/CLAUDE.md", text)

    def test_verification_agent_uses_parent_authorized_xwiki_handoff(self):
        agent = (ROOT / ".claude/agents/soc-verification-engineer.md").read_text(
            encoding="utf-8"
        )
        recovery = (ROOT / ".claude/rules/11_verif_recovery_gate.md").read_text(
            encoding="utf-8"
        )
        environment = (ROOT / "env/env.sh").read_text(encoding="utf-8")

        self.assertIn("export XWIKI_DIR=", environment)
        self.assertIn("query the persistent xwiki", agent)
        self.assertIn("never guess a wiki path", agent)
        self.assertIn("xwiki writeback candidate", agent)
        self.assertIn("parent session", agent)
        self.assertIn("external wiki directly", agent)
        self.assertIn("edit only `hw/dv/**`", agent)
        for classification in ("env_bug", "rtl_bug", "spec_bug"):
            self.assertIn(classification, agent)
            self.assertIn(classification, recovery)
        self.assertIn("write authorization", recovery)
        self.assertIn("child agent must not write", recovery)


if __name__ == "__main__":
    unittest.main()
