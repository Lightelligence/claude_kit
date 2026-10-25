"""Replay a real kit hash bug; no EDA, model invocation or Git mutation.

Requires local Git objects for the historical fix 59a766b (PR #14).
Outputs must go to a NEW directory. This proves narrow evidence-checking
behavior, not skill quality or DV-project usefulness.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from claude_kit.experiment import scope_snapshot
from claude_kit.fix_validation import report
from claude_kit.variants import search


PROBE = '''import hashlib, json, sys
from pathlib import Path
from helper import Helper
root = Path(sys.argv[1])
case, side = sys.argv[2:4]
contents = {"reproducer": "one\\n", "variant": "one\\ntwo\\n", "control": "plain", "regression": ""}
ref = Helper(root).artifact("out/" + side + "-" + case + ".txt", contents[case])
actual = hashlib.sha256((root / ref["path"]).read_bytes()).hexdigest()
passed = ref["sha256"] == actual
print(json.dumps({"case": case, "passed": passed, "expected_digest": actual,
                  "recorded_digest": ref["sha256"], "failure_signature": "" if passed else "persisted_digest_mismatch"}))
sys.exit(0 if passed else 1)
'''


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True).stdout


def helper(revision):
    source = git("show", f"{revision}:tests/test_dv.py").decode()
    tree = ast.parse(source)
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "artifact")
    selected = textwrap.dedent("\n".join(source.splitlines()[method.lineno - 1:method.end_lineno]))
    prefix = '''import hashlib
class Helper:
    def __init__(self, root):
        self.root = root
    def write(self, path, content):
        # Explicitly replay Windows newline persistence on every host.
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.replace("\\n", "\\r\\n").encode("utf-8"))
'''
    return prefix + textwrap.indent(selected, "    ") + "\n", hashlib.sha256(source.encode()).hexdigest()


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    (output / "source").mkdir()
    (output / "out").mkdir()
    profile = {"project": {"id": "kit-historical-hash-replay"}}

    def write(path, value):
        target = output / path
        target.write_text(value if isinstance(value, str) else json.dumps(value, indent=2), encoding="utf-8", newline="\n")
        return {"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    revisions = {side: git("rev-parse", ref).decode().strip()
                 for side, ref in (("base", "59a766b^"), ("patched", "59a766b"))}
    snapshots, runs, source_hashes = {}, [], {}
    write("source/probe.py", PROBE)
    variant_report = None
    for side, revision in revisions.items():
        content, source_hashes[side] = helper(revision)
        write("source/helper.py", content)
        snapshots[side] = scope_snapshot(output, profile, ["source"])
        if side == "base":
            line = next(i for i, value in enumerate(content.splitlines(), 1) if "hashlib.sha256(content.encode())" in value)
            plan = {"schema_version": 1, "project": profile["project"]["id"], "id": "hash-replay",
                    "root_cause": "Hashing text before newline persistence differs from hashing on-disk bytes.",
                    "known_instance": {"path": "source/helper.py", "line": line}, "scope": ["source"],
                    "patterns": [{"id": "exact", "literal": "hashlib.sha256(content.encode())", "rationale": "Known historical bug"},
                                 {"id": "family", "literal": "hashlib.sha256(", "rationale": "Inspect other hashing sites; byte hashing is a counterexample"}]}
            write("variants.json", plan)
            variant_report = search(output, profile, plan)
            write("out/variant-candidates.json", variant_report)
        for kind in ("reproducer", "variant", "control", "regression"):
            command = [sys.executable, "-B", "source/probe.py", ".", kind, side]
            result = subprocess.run(command, cwd=output, capture_output=True, text=True, timeout=10)
            if result.returncode not in (0, 1) or not result.stdout.strip():
                raise RuntimeError(f"Historical replay failed to run: {result.stderr}")
            observation = json.loads(result.stdout)
            ref = write(f"out/{side}-{kind}.json", observation)
            runs.append({"schema_version": 1, "project": profile["project"]["id"], "fix_id": "hash-replay",
                         "check_id": kind, "side": side, "run_id": f"{side}-{kind}", "test": kind,
                         "configuration": "explicit-crlf-persistence", "seed": None,
                         "tool_version": sys.version.split()[0], "command": command,
                         "baseline": snapshots[side], "status": "passed" if result.returncode == 0 else "failed",
                         "complete": True, "failure_signature": observation["failure_signature"], "artifacts": [ref]})
    review = write("out/triage.json", {"reviewer": "controlled-history-replay",
        "known_bug": "source/helper.py: text hash before persistence",
        "counterexample": "source/probe.py: hashing read_bytes is correct",
        "limitations": "Only this replay scope was reviewed; no semantic variant recognition or EDA claim."})
    plan = {"schema_version": 1, "project": profile["project"]["id"], "id": "hash-replay",
            "root_cause": "Text hash does not match persisted CRLF bytes", "inputs": ["source"],
            **snapshots, "variant_review": {"status": "reviewed", "reviewer": "controlled-history-replay",
                "rationale": "Known historical instance plus correct byte-hash counterexample", "artifacts": [review]},
            "checks": [{"id": kind, "kind": kind, "test": kind, "configuration": "explicit-crlf-persistence", "seed": None,
                        **({"failure_signature": "persisted_digest_mismatch"} if kind in ("reproducer", "variant") else {})}
                       for kind in ("reproducer", "variant", "control", "regression")]}
    write("fix-plan.json", plan)

    def assess(records):
        paths = []
        for index, value in enumerate(records):
            path = f"out/run-{index}.json"
            write(path, value)
            paths.append(path)
        return report(output, profile, "fix-plan.json", paths)

    correct = assess(runs)
    write("out/fix-report.json", correct)
    wrong_signature = copy.deepcopy(runs)
    wrong_signature[0]["failure_signature"] = "unrelated_test_failure"
    wrong_seed = copy.deepcopy(runs)
    wrong_seed[4]["seed"] = 99
    controls = {"unrelated_failure": assess(wrong_signature)["status"],
                "different_seed": assess(wrong_seed)["status"],
                "omitted_regression": assess(runs[:-1])["status"]}
    assess(runs)  # Leave the real, complete record set on disk.
    summary = {"measurement": "Real historical code replay with explicit CRLF persistence; no model or EDA execution",
               "historical_commits": revisions, "historical_file_sha256": source_hashes,
               "actual_runs": [{"run_id": r["run_id"], "status": r["status"]} for r in runs],
               "fix_status": correct["status"], "negative_controls": controls,
               "variant_candidates": variant_report["candidates"],
               "skill_effectiveness": "not_measured", "dv_project_usefulness": "not_measured", "merge_criteria_met": False}
    if correct["status"] != "ready_for_review" or set(controls.values()) != {"gaps"}:
        raise AssertionError("Historical fix/negative-control assessment disagrees with the known results")
    write("summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(run(parser.parse_args().output.resolve()), indent=2))
