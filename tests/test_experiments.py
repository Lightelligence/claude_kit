from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_kit.cli import main
from claude_kit.core import KitError
from claude_kit.experiment import digest, load, scope_snapshot
from claude_kit.fix_validation import report as fix_report
from claude_kit.skill_eval import report as eval_report, snapshot as eval_snapshot
from claude_kit.variants import search


class ExperimentFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = {"project": {"id": "block"}, "permissions": {"forbidden": ["secrets/**"]}}
        self.write(".ai/project.json", self.profile)
        self.write("source/dut.sv", "module dut; endmodule\n")
        self.write("skills/debug/SKILL.md", "Use evidence.\n")

    def write(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return path

    def ref(self, path, value):
        target = self.write(path, value)
        return {"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    def cli(self, arguments):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = main([*arguments, "--project-root", str(self.root), "--profile", ".ai/project.json"])
        return status, output.getvalue(), errors.getvalue()


class SkillEvaluationTests(ExperimentFixture):
    def setUp(self):
        super().setUp()
        self.suite = {"schema_version": 1, "project": "block", "id": "debug", "inputs": ["source"],
                      "repetitions": 2, "arms": {"baseline": {"label": "without", "skill_inputs": []},
                      "candidate": {"label": "with", "skill_inputs": ["skills/debug"]}}, "cases": [{
                          "id": "route", "prompt": "Inspect a DV-only change without executing EDA.",
                          "assertions": [{"id": "routing", "artifact": "observations", "operator": "json_equals",
                                          "pointer": "/recommended_checks", "expected": ["dv_compile"]}]}]}
        self.current = eval_snapshot(self.root, self.profile, self.suite)
        self.runs = []
        for repetition in (1, 2):
            for arm in ("baseline", "candidate"):
                run_id = f"{arm}-{repetition}"
                ref = self.ref(f"out/{run_id}.json", {"recommended_checks": ["dv_compile"] if arm == "candidate" else ["rtl_lint"]})
                self.runs.append({"schema_version": 1, "project": "block", "suite_id": "debug", "case_id": "route",
                    "run_id": run_id, "arm": arm, "repetition": repetition, "status": "completed", "model": "fixture-model",
                    "environment_id": "fixture-env", "settings_digest": digest({"effort": "same"}),
                    "suite_digest": self.current["suite_digest"], "input_digest": self.current["input_digest"],
                    "skill_digest": self.current["skill_digests"][arm], "outputs": {"observations": ref,
                        "transcript": self.ref(f"out/{run_id}.trace.json", {"fixture": True, "tool_calls": []})},
                    "metrics": {"tokens": 100 if arm == "candidate" else 150, "duration_seconds": None, "tool_calls": 2}})

    def result(self, runs=None):
        self.write("suite.json", self.suite)
        paths = []
        for index, run in enumerate(self.runs if runs is None else runs):
            paths.append(f"out/run-{index}.json")
            self.write(paths[-1], run)
        return eval_report(self.root, self.profile, "suite.json", paths)

    def test_paired_behavior_grading_and_unknown_metrics(self):
        result = self.result()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["summary"]["baseline_pass_rate"], 0)
        self.assertEqual(result["summary"]["candidate_pass_rate"], 1)
        self.assertEqual(result["metric_deltas"]["tokens"], {"count": 2, "mean": -50, "stdev": 0})
        self.assertIsNone(result["metric_deltas"]["duration_seconds"]["mean"])
        for offset in (0, 2):
            self.runs[offset]["outputs"], self.runs[offset + 1]["outputs"] = self.runs[offset + 1]["outputs"], self.runs[offset]["outputs"]
        regressed = self.result()
        self.assertEqual(regressed["status"], "complete")
        self.assertEqual(regressed["pass_rate_delta"], -1)

    def test_missing_pair_or_failed_execution_is_not_comparable(self):
        self.assertEqual(self.result(self.runs[:-1])["status"], "gaps")
        self.runs[0]["status"] = "infra_error"
        result = self.result()
        self.assertEqual(result["summary"]["comparable_pairs"], 1)
        self.assertEqual(result["status"], "gaps")

    def test_mismatched_model_settings_and_environment(self):
        for field, value in (("model", "other-model"), ("environment_id", "other-env"), ("settings_digest", "f" * 64)):
            with self.subTest(field=field):
                runs = copy.deepcopy(self.runs)
                runs[1][field] = value
                self.assertIn(f"unpaired_{field}", self.result(runs)["pairs"][0]["gaps"])

    def test_fixture_skill_or_suite_change_invalidates_saved_runs(self):
        self.write("source/new.sv", "new input")
        self.assertEqual(self.result()["summary"]["comparable_pairs"], 0)
        (self.root / "source/new.sv").unlink()
        self.write("skills/debug/SKILL.md", "Changed guidance.")
        self.assertEqual(self.result()["summary"]["comparable_pairs"], 0)
        self.write("skills/debug/SKILL.md", "Use evidence.\n")
        self.suite["cases"][0]["prompt"] += " Changed task."
        self.assertEqual(self.result()["summary"]["comparable_pairs"], 0)
        self.suite["cases"][0]["prompt"] = self.suite["cases"][0]["prompt"].removesuffix(" Changed task.")
        self.write(self.runs[1]["outputs"]["observations"]["path"], "tampered")
        self.assertIn("candidate:changed_artifact:out/candidate-1.json", self.result()["pairs"][0]["gaps"])

    def test_malformed_or_unproduced_model_output_counts_as_quality_failure(self):
        self.runs[1]["outputs"]["observations"] = self.ref("out/malformed.json", "not JSON")
        self.runs[3]["outputs"].pop("observations")
        result = self.result()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["summary"]["candidate_pass_rate"], 0)
        self.assertEqual(result["summary"]["comparable_pairs"], 2)

    def test_missing_transcript_is_an_evidence_gap(self):
        self.runs[1]["outputs"].pop("transcript")
        result = self.result()
        self.assertEqual(result["status"], "gaps")
        self.assertIn("candidate:missing_transcript", result["pairs"][0]["gaps"])

    def test_json_boolean_does_not_match_integer(self):
        self.suite["cases"][0]["assertions"][0]["pointer"] = "/flag"
        self.suite["cases"][0]["assertions"][0]["expected"] = False
        self.current = eval_snapshot(self.root, self.profile, self.suite)
        for run in self.runs:
            run["suite_digest"] = self.current["suite_digest"]
            run["outputs"]["observations"] = self.ref(f"out/{run['run_id']}.json", {"flag": 0})
        result = self.result()
        self.assertEqual(result["summary"]["candidate_pass_rate"], 0)

    def test_duplicate_records_and_invalid_metrics_rejected(self):
        with self.assertRaisesRegex(KitError, "Duplicate"):
            self.result([*self.runs, self.runs[0]])
        self.runs[0]["metrics"]["tokens"] = True
        with self.assertRaisesRegex(KitError, "finite non-negative"):
            self.result()

    def test_cli_and_no_tool_execution(self):
        self.result()
        with patch("subprocess.run", side_effect=AssertionError("no execution")):
            code, output, _ = self.cli(["skill-eval", "report", "--suite", "suite.json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output)["summary"]["comparable_pairs"], 0)
        code, output, _ = self.cli(["skill-eval", "snapshot", "--suite", "suite.json"])
        self.assertEqual(code, 0)
        self.assertIn("skill_digests", json.loads(output))


class FixValidationTests(ExperimentFixture):
    def setUp(self):
        super().setUp()
        before = scope_snapshot(self.root, self.profile, ["source"])
        self.write("source/dut.sv", "module fixed_dut; endmodule\n")
        after = scope_snapshot(self.root, self.profile, ["source"])
        review_ref = self.ref("out/triage.json", {"reviewer": "fixture-reviewer", "candidates": [], "limitations": "literal fixture only"})
        self.plan = {"schema_version": 1, "project": "block", "id": "B1", "root_cause": "Unguarded read pointer update",
                     "inputs": ["source"], "base": before, "patched": after,
                     "variant_review": {"status": "reviewed", "reviewer": "fixture-reviewer", "rationale": "Reviewed scoped candidates", "artifacts": [review_ref]},
                     "checks": [{"id": kind, "kind": kind, "test": kind, "configuration": "default", "seed": 42,
                                 **({"failure_signature": "empty_read"} if kind in ("reproducer", "variant") else {})}
                                for kind in ("reproducer", "variant", "control", "regression")]}
        self.runs = []
        for check in self.plan["checks"]:
            for side in ("base", "patched"):
                fail = side == "base" and check["kind"] in ("reproducer", "variant")
                run_id = f"{check['id']}-{side}"
                self.runs.append({"schema_version": 1, "project": "block", "fix_id": "B1", "check_id": check["id"],
                    "side": side, "run_id": run_id, "test": check["test"], "configuration": "default", "seed": 42,
                    "tool_version": "fixture-tool", "command": ["fixture", "--arg", "same", "--arg", "same"],
                    "baseline": self.plan[side], "complete": True, "status": "failed" if fail else "passed",
                    "failure_signature": "empty_read" if fail else "",
                    "artifacts": [self.ref(f"out/{run_id}.json", {"run_id": run_id, "failed": fail})]})

    def result(self, runs=None):
        self.write("fix.json", self.plan)
        paths = []
        for index, run in enumerate(self.runs if runs is None else runs):
            paths.append(f"out/run-{index}.json")
            self.write(paths[-1], run)
        return fix_report(self.root, self.profile, "fix.json", paths)

    def test_paired_fix_control_variant_regression_ready_never_signoff(self):
        result = self.result()
        self.assertEqual(result["status"], "ready_for_review")
        self.assertFalse(result["signoff"])
        self.assertEqual(result["summary"]["ready_for_review"], 4)

    def test_infrastructure_failure_is_not_bug_reproduction(self):
        for status, signature in (("infra_error", "empty_read"), ("failed", "license_checkout"), ("passed", "")):
            with self.subTest(status=status, signature=signature):
                self.runs[0].update(status=status, failure_signature=signature)
                self.assertEqual(self.result()["status"], "gaps")

    def test_seed_tool_input_or_configuration_mismatch_is_gap(self):
        for field, value in (("seed", 43), ("tool_version", "different"), ("configuration", "wide"),
                             ("baseline", {"input_digest": "a" * 64, "source_revision": None})):
            with self.subTest(field=field):
                runs = copy.deepcopy(self.runs)
                runs[1][field] = value
                self.assertEqual(self.result(runs)["status"], "gaps")

    def test_missing_control_or_regression_run_blocks_ready(self):
        self.assertEqual(self.result(self.runs[:-1])["status"], "gaps")
        self.runs[-1]["status"] = "failed"
        self.assertEqual(self.result()["status"], "gaps")

    def test_source_or_artifact_change_invalidates_fix_evidence(self):
        self.write("source/new.sv", "changed source")
        self.assertIn("stale_patched_input_digest", self.result()["gaps"])
        (self.root / "source/new.sv").unlink()
        self.write(self.runs[0]["artifacts"][0]["path"], "tampered")
        self.assertEqual(self.result()["status"], "gaps")

    def test_variant_review_is_explicit_and_optional_variant_checks_need_justification(self):
        self.plan["variant_review"]["status"] = "pending"
        self.assertIn("variant_review_required", self.result()["gaps"])
        self.plan["variant_review"]["status"] = "reviewed"
        self.plan["checks"] = [c for c in self.plan["checks"] if c["kind"] != "variant"]
        self.assertEqual(self.result([r for r in self.runs if r["check_id"] != "variant"])["status"], "ready_for_review")

    def test_duplicate_run_and_missing_required_check_kind_rejected(self):
        with self.assertRaisesRegex(KitError, "Duplicate"):
            self.result([*self.runs, self.runs[0]])
        self.plan["checks"] = self.plan["checks"][:1]
        with self.assertRaisesRegex(KitError, "requires reproducer"):
            self.result([])

class VariantTests(ExperimentFixture):
    def setUp(self):
        super().setUp()
        self.write("rtl/a.sv", "if (rd_en) ptr++;\n")
        self.write("rtl/b.sv", "if (rd_en && !empty) ptr++;\n")
        self.plan = {"schema_version": 1, "project": "block", "id": "B1", "root_cause": "Unguarded read",
                     "known_instance": {"path": "rtl/a.sv", "line": 1}, "scope": ["rtl"],
                     "patterns": [{"id": "exact", "literal": "if (rd_en)", "rationale": "known instance"},
                                  {"id": "family", "literal": "rd_en", "rationale": "broaden guard"}]}

    def test_anchor_then_generalization_only_returns_candidates(self):
        result = search(self.root, self.profile, self.plan)
        self.assertTrue(result["search_complete"])
        self.assertIsNone(result["confirmed_bugs"])
        self.assertEqual({c["path"] for c in result["candidates"]}, {"rtl/a.sv", "rtl/b.sv"})
        self.assertTrue(all(c["verdict"] == "unreviewed" for c in result["candidates"]))

    def test_anchor_must_match_the_declared_line_and_scope(self):
        for line, scope in ((2, ["rtl"]), (1, ["source"])):
            with self.subTest(line=line, scope=scope):
                self.plan["known_instance"]["line"], self.plan["scope"] = line, scope
                with self.assertRaises(KitError):
                    search(self.root, self.profile, self.plan)

    def test_file_match_and_byte_budgets_report_incompleteness(self):
        for limits in ({"max_files": 1}, {"max_matches": 1}, {"max_scan_bytes": 20}):
            with self.subTest(limits=limits):
                self.assertFalse(search(self.root, self.profile, self.plan, **limits)["search_complete"])

    def test_forbidden_path_is_not_read_and_partial_scope_is_visible(self):
        self.write("rtl/private.sv", "secret-value")
        self.profile["permissions"]["forbidden"].append("rtl/private.sv")
        result = search(self.root, self.profile, self.plan)
        self.assertFalse(result["search_complete"])
        self.assertNotIn("secret-value", json.dumps(result))
        self.assertIn("forbidden_path:rtl/private.sv", result["gaps"])

    @unittest.skipIf(os.name == "nt", "Windows symlink privileges vary")
    def test_symlink_candidates_are_not_followed(self):
        (self.root / "rtl/link.sv").symlink_to(self.root / "source/dut.sv")
        result = search(self.root, self.profile, self.plan)
        self.assertFalse(result["search_complete"])
        self.assertIn("unscanned_symlink:rtl/link.sv", result["gaps"])

    def test_cli_no_mutation_or_execution(self):
        self.write("variants.json", self.plan)
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch("subprocess.run", side_effect=AssertionError("no execution")):
            code, output, _ = self.cli(["dv", "variant-search", "--plan", "variants.json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["search_complete"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})


class RecordBoundaryTests(ExperimentFixture):
    def test_strict_json(self):
        for value in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', '[]'):
            self.write("bad.json", value)
            with self.subTest(value=value), self.assertRaises(KitError):
                load(self.root, self.profile, "bad.json")

    def test_forbidden_oversized_and_traversing_records_rejected(self):
        self.write("secrets/data.json", {})
        self.write("huge.json", " " * 1_000_001)
        for value in ("secrets/data.json", "huge.json", "../outside.json", str(self.root / "huge.json")):
            with self.subTest(value=value), self.assertRaises(KitError):
                load(self.root, self.profile, value)

if __name__ == "__main__":
    unittest.main()
