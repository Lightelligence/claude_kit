from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from claude_kit.core import KitError, sync_project_skills
from claude_kit.dv import load_json, markdown_report, report, snapshot


class DvEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = {"project": {"id": "block"}, "permissions": {"forbidden": ["secrets/**"]}}
        self.write(".ai/project.json", self.profile)
        self.write("source/rtl.sv", "module dut; endmodule\n")
        self.write("source/spec.md", "Reset cancels requests.\n")
        self.plan = {"schema_version": 1, "project": "block", "inputs": ["source"], "requirements": [{
            "id": "R1", "statement": "Reset cancels outstanding requests", "spec_ref": "source/spec.md",
            "configurations": ["default"], "open_questions": [], "open_bugs": [], "cases": [{
                "id": "reset", "method": "simulation", "test": "reset_test", "checkers": ["scoreboard"],
                "coverage_targets": ["reset_nonempty"], "require_negative_control": True}]}]}
        self.write("plan.json", self.plan)
        self.ref = self.artifact("out/result.txt", "Fixture only: checker active; target hit; injected bug detected.\n")
        self.run = {"schema_version": 1, "project": "block", "run_id": "run1", "requirement_id": "R1",
                    "case_id": "reset", "configuration": "default", "method": "simulation", "test": "reset_test",
                    "seed": 42, "tool_version": "fixture", "command": ["fixture-runner", "--seed", "42"],
                    "baseline": snapshot(self.root, self.profile, self.plan), "status": "passed", "complete": True,
                    "artifacts": [self.ref], "checkers": [{"id": "scoreboard", "status": "passed", "active": True,
                    "artifacts": [self.ref], "negative_control": {"detected": True, "artifacts": [self.ref]}}],
                    "coverage": [{"id": "reset_nonempty", "hit": True, "complete": True, "artifacts": [self.ref]}]}

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def artifact(self, path, content):
        self.write(path, content)
        # Hash persisted bytes, including platform newline conversion, just as
        # a real result collector must do for the artifact integrity contract.
        return {"path": path, "sha256": hashlib.sha256((self.root / path).read_bytes()).hexdigest()}

    def result(self, *runs):
        self.write("plan.json", self.plan)
        paths = []
        for i, run in enumerate(runs):
            path = f"out/run{i}.json"
            self.write(path, run)
            paths.append(path)
        return report(self.root, self.profile, "plan.json", paths)

    def refresh(self):
        self.run["baseline"] = snapshot(self.root, self.profile, self.plan)

    def test_complete_evidence_is_review_ready_never_signoff(self):
        result = self.result(self.run)
        self.assertEqual(result["status"], "ready_for_review")
        self.assertFalse(result["signoff"])
        self.assertEqual(result["rows"][0]["accepted_runs"], ["run1"])

    def test_crlf_artifact_hashes_use_persisted_bytes(self):
        content = b"checker active\r\ntarget hit\r\n"
        (self.root / "out/result.txt").write_bytes(content)
        self.ref["sha256"] = hashlib.sha256(content).hexdigest()
        self.assertEqual(self.result(self.run)["status"], "ready_for_review")
        self.ref["sha256"] = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
        self.assertEqual(self.result(self.run)["status"], "gaps")

    def test_all_configurations_and_cases_are_required(self):
        self.plan["requirements"][0]["configurations"].append("wide")
        self.plan["requirements"][0]["cases"].append({**self.plan["requirements"][0]["cases"][0], "id": "recovery"})
        self.refresh()
        result = self.result(self.run)
        self.assertEqual(result["summary"], {"total": 4, "ready_for_review": 1, "gaps": 3})

    def test_uncommitted_changes_and_new_input_files_invalidate_runs(self):
        for path in ("source/rtl.sv", "source/new_config.txt", "source/spec.md"):
            with self.subTest(path=path):
                self.write(path, "changed\n")
                self.assertIn("stale_evidence", self.result(self.run)["rows"][0]["gaps"])

    def test_mapping_and_revision_changes_invalidate_runs(self):
        self.run["baseline"]["source_revision"] = "different-revision"
        self.assertEqual(self.result(self.run)["rows"][0]["stale_runs"], ["run1"])
        self.refresh()
        self.plan["requirements"][0]["statement"] += " after edge"
        self.assertIn("stale_evidence", self.result(self.run)["rows"][0]["gaps"])

    def test_output_changes_do_not_invalidate_source_snapshot(self):
        previous = snapshot(self.root, self.profile, self.plan)
        self.write("out/new-run.log", "unrelated output")
        self.assertEqual(previous, snapshot(self.root, self.profile, self.plan))
        (self.root / "source/spec.md").unlink()
        self.assertNotEqual(previous["input_digest"], snapshot(self.root, self.profile, self.plan)["input_digest"])

    def test_distinct_cases_in_one_physical_run_are_supported(self):
        second_case = {**self.plan["requirements"][0]["cases"][0], "id": "recovery"}
        self.plan["requirements"][0]["cases"].append(second_case)
        self.refresh()
        second = {**self.run, "case_id": "recovery"}
        result = self.result(self.run, second)
        self.assertEqual(result["status"], "ready_for_review")
        self.assertEqual(result["summary"]["ready_for_review"], 2)

    def test_unresolved_semantics_bugs_and_empty_mappings_remain_gaps(self):
        req = self.plan["requirements"][0]
        req["open_questions"] = ["priority?"]
        req["open_bugs"] = ["BUG-17"]
        req["cases"][0]["checkers"] = []
        req["cases"][0]["coverage_targets"] = []
        self.refresh()
        self.assertEqual(self.result(self.run)["rows"][0]["gaps"], [
            "unresolved_questions", "open_bugs", "missing_checker_mapping", "missing_coverage_mapping"])

    def test_no_log_or_changed_log_cannot_pass(self):
        self.write("out/result.txt", "different content")
        result = self.result(self.run)
        self.assertEqual(result["status"], "gaps")
        self.assertIn("changed_artifact:out/result.txt", result["rows"][0]["rejected_runs"][0]["issues"])
        (self.root / "out/result.txt").unlink()
        self.assertEqual(self.result(self.run)["status"], "gaps")

    def test_every_non_success_state_blocks_despite_passing_seed(self):
        for status in ("failed", "compile_error", "timeout", "infra_error", "running", "skipped", "unknown"):
            failed = copy.deepcopy(self.run)
            failed.update(run_id="run2", status=status)
            with self.subTest(status=status):
                self.assertEqual(self.result(self.run, failed)["status"], "gaps")

    def test_inactive_checker_partial_coverage_negative_control_and_incomplete_run(self):
        for location, key, value in (("checkers", "active", False), ("coverage", "complete", False),
                                     ("coverage", "hit", False), ("checkers", "status", "unknown")):
            run = copy.deepcopy(self.run)
            run[location][0][key] = value
            with self.subTest(location=location, key=key):
                self.assertEqual(self.result(run)["status"], "gaps")
        self.run["checkers"][0]["negative_control"]["detected"] = False
        self.assertEqual(self.result(self.run)["status"], "gaps")
        self.run["complete"] = False
        self.assertEqual(self.result(self.run)["status"], "gaps")

    def test_formal_requires_unbounded_nonvacuous_reviewed_proof(self):
        case = self.plan["requirements"][0]["cases"][0]
        case.update(method="formal", require_negative_control=False)
        self.run.update(method="formal", status="proven")
        self.run["checkers"][0]["status"] = "proven"
        self.run["formal"] = {"scope": "dut/default", "unbounded": True, "nonvacuous": True,
                              "assumptions_reviewed": True, "artifacts": [self.ref]}
        self.refresh()
        self.assertEqual(self.result(self.run)["status"], "ready_for_review")
        for field in ("unbounded", "nonvacuous", "assumptions_reviewed"):
            run = copy.deepcopy(self.run)
            run["formal"][field] = False
            self.assertEqual(self.result(run)["status"], "gaps")
        for status in ("passed", "inconclusive", "counterexample", "timeout"):
            self.run["status"] = status
            self.assertEqual(self.result(self.run)["status"], "gaps")

    def test_invalid_identity_duplicates_and_types_are_errors(self):
        for field, value in (("project", "wrong"), ("case_id", "missing"), ("test", "wrong"),
                             ("configuration", "wrong"), ("seed", True), ("complete", "true"),
                             ("checkers", {}), ("status", "pass"), ("baseline", [])):
            run = {**self.run, field: value}
            with self.subTest(field=field), self.assertRaises(KitError):
                self.result(run)
        with self.assertRaisesRegex(KitError, "Duplicate run"):
            self.result(self.run, self.run)
        self.plan["requirements"].append(copy.deepcopy(self.plan["requirements"][0]))
        with self.assertRaisesRegex(KitError, "duplicates"):
            self.result()

    def test_json_limits_duplicate_keys_and_nonobject_rejected(self):
        for text in ('{"x":1,"x":2}', '[]', ' ' * 1000001):
            self.write("bad.json", text)
            with self.assertRaises(KitError):
                load_json(self.root, self.profile, "bad.json")

    def test_local_escape_symlink_and_forbidden_paths_rejected(self):
        for path in ("../escape", "/etc/passwd", "secrets/key", ".git/config"):
            self.run["artifacts"] = [{**self.ref, "path": path}]
            with self.subTest(path=path), self.assertRaises(KitError):
                self.result(self.run)
        (self.root / "out/link").symlink_to(self.root.parent)
        self.run["artifacts"] = [{**self.ref, "path": "out/link/escape"}]
        with self.assertRaises(KitError):
            self.result(self.run)
        (self.root / "source/link").symlink_to(self.root / "source/rtl.sv")
        with self.assertRaisesRegex(KitError, "Symlinks"):
            snapshot(self.root, self.profile, self.plan)

    def test_external_artifacts_are_limited_to_declared_regression_root(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory).resolve()
            (external / "result.txt").write_text("evidence")
            self.profile["artifacts"] = {"regression": {"root": str(external)}}
            ref = {"path": "regression:result.txt", "sha256": hashlib.sha256(b"evidence").hexdigest()}
            self.run["artifacts"] = [ref]
            self.assertEqual(self.result(self.run)["status"], "ready_for_review")
            self.run["artifacts"][0]["path"] = "regression:../escape"
            with self.assertRaises(KitError):
                self.result(self.run)

    def test_cli_exit_codes_and_read_only_behavior(self):
        self.result(self.run)
        args = [sys.executable, str(ROOT / "bin/claude-kit"), "dv", "report", "--project-root", str(self.root),
                "--plan", "plan.json", "--run", "out/run0.json"]
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        process = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertFalse(json.loads(process.stdout)["signoff"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.run["status"] = "failed"
        self.result(self.run)
        self.assertEqual(subprocess.run(args, capture_output=True).returncode, 1)
        self.run["complete"] = "true"
        self.result_invalid_write()
        self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)

    def result_invalid_write(self):
        self.write("out/run0.json", self.run)

    def test_missing_runs_markdown_and_template_entrypoints(self):
        result = self.result()
        self.assertIn("missing_run", result["rows"][0]["gaps"])
        self.assertIn("| R1 | default | reset | gaps | missing_run |", markdown_report(result))
        self.assertIn(result["baseline"]["input_digest"], markdown_report(result))
        for kind in ("plan", "run"):
            process = subprocess.run([sys.executable, str(ROOT / "bin/claude-kit"), "dv", "template", kind],
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)["schema_version"], 1)

    def test_skill_references_sync_to_consumer(self):
        sync_project_skills(self.root)
        reference = self.root / ".claude/skills/dv-engineering/references/requirement-flow.md"
        self.assertTrue(reference.is_file())


if __name__ == "__main__":
    unittest.main()
