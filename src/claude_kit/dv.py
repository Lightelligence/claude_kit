"""Requirement-level evidence joins; no EDA execution or signoff decisions.

The project adapter owns result extraction. This module verifies the declared
scope, artifact integrity and evidence completeness, not hardware semantics.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .core import KitError, MAX_ARTIFACT_BYTES, _permission_match, _project_path, read_artifact


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KitError(f"{label} must be a non-empty string")
    return value


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not empty):
        raise KitError(f"{label} must be a {'possibly empty' if empty else 'non-empty'} list")
    for item in value:
        _text(item, label)
    if len(value) != len(set(value)):
        raise KitError(f"{label} contains duplicates")
    return value


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise KitError(f"{label} must be an object")
    return value


def _objects(value: Any, label: str, *, empty: bool = False) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (not value and not empty):
        raise KitError(f"{label} must be a {'possibly empty' if empty else 'non-empty'} list")
    for item in value:
        _object(item, label)
    return value


def _local_path(root: Path, profile: dict, value: str) -> Path:
    _text(value, "path")
    if Path(value).is_absolute():
        raise KitError(f"Expected project-relative path: {value}")
    path = _project_path(root, value, "DV path")
    forbidden = profile.get("permissions", {}).get("forbidden", [])
    if any(_permission_match(p, forbidden) for p in (value, path.relative_to(root.resolve()).as_posix())):
        raise KitError(f"Forbidden DV path: {value}")
    if ".git" in Path(value).parts or ".git" in path.parts:
        raise KitError("DV inputs and artifacts must not include .git")
    return path


def load_json(root: Path, profile: dict, path: str) -> dict:
    _local_path(root, profile, path)
    artifact = read_artifact(root, path, MAX_ARTIFACT_BYTES)
    if artifact["truncated"]:
        raise KitError(f"DV JSON exceeds {MAX_ARTIFACT_BYTES} bytes: {path}")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise KitError(f"Duplicate JSON key {key}: {path}")
            result[key] = value
        return result
    return _object(json.loads(artifact["text"], object_pairs_hook=unique), path)


def validate_plan(plan: dict, profile: dict) -> None:
    if type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
        raise KitError("DV plan schema_version must be 1")
    if plan.get("project") != profile.get("project", {}).get("id") or not plan.get("project"):
        raise KitError("DV plan project must match profile project.id")
    _strings(plan.get("inputs"), "inputs")
    requirements = _objects(plan.get("requirements"), "requirements")
    ids = []
    for req in requirements:
        ids.append(_text(req.get("id"), "requirement.id"))
        for field in ("statement", "spec_ref"):
            _text(req.get(field), f"{req['id']}.{field}")
        _strings(req.get("configurations"), f"{req['id']}.configurations")
        for field in ("open_questions", "open_bugs"):
            _strings(req.get(field), f"{req['id']}.{field}", empty=True)
        cases = _objects(req.get("cases"), f"{req['id']}.cases")
        case_ids = []
        for case in cases:
            case_ids.append(_text(case.get("id"), "case.id"))
            if case.get("method") not in ("simulation", "formal"):
                raise KitError("case.method must be simulation or formal")
            _text(case.get("test"), "case.test")
            # Empty mappings are valid planning gaps, never closure evidence.
            _strings(case.get("checkers"), "case.checkers", empty=True)
            _strings(case.get("coverage_targets"), "case.coverage_targets", empty=True)
            if type(case.get("require_negative_control")) is not bool:
                raise KitError("case.require_negative_control must be boolean")
        _strings(case_ids, f"{req['id']}.case IDs")
    _strings(ids, "requirement IDs")


def _digest(path: Path) -> str:
    if not path.is_file():
        raise KitError(f"Expected a regular evidence/input file: {path}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot(root: Path, profile: dict, plan: dict) -> dict:
    """Hash declared source trees and the plan, including untracked input files.

    Store outputs outside these trees. A new/deleted file changes the digest.
    No Git index, working tree, runner state or project file is modified.
    """
    validate_plan(plan, profile)
    files = {}
    for value in plan["inputs"]:
        path = _local_path(root, profile, value)
        if path.is_symlink() or (root / value).is_symlink():
            raise KitError(f"Use the real input path instead of a symlink: {value}")
        if not path.exists():
            raise KitError(f"Missing DV input: {value}")
        candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_symlink():
                raise KitError(f"Symlinks in DV input trees are unsupported: {candidate}")
            relative = candidate.relative_to(root.resolve()).as_posix()
            checked = _local_path(root, profile, relative)
            if checked.is_file():
                if len(files) >= 20000 and relative not in files:
                    raise KitError("DV scope exceeds 20000 files; select a smaller block")
                files[relative] = _digest(checked)
    if not files:
        raise KitError("DV inputs must contain at least one file")
    payload = json.dumps({"plan": plan, "files": files}, sort_keys=True, separators=(",", ":"))
    revision = None
    if (root / ".git").exists():
        try:
            result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                    capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                revision = result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"project": plan["project"], "source_revision": revision,
            "input_digest": hashlib.sha256(payload.encode()).hexdigest(), "files": files}


def _artifact_path(root: Path, profile: dict, value: str) -> Path:
    if value.startswith("regression:"):
        configured = profile.get("artifacts", {}).get("regression", {}).get("root")
        if not configured or not Path(configured).is_absolute():
            raise KitError("regression: artifact requires an absolute artifacts.regression.root")
        relative = value[len("regression:"):]
        if not relative or Path(relative).is_absolute() or ".git" in Path(relative).parts:
            raise KitError("regression: artifact must be relative to the configured root")
        return _project_path(Path(configured), relative, "regression artifact")
    return _local_path(root, profile, value)


def _artifact_issues(root: Path, profile: dict, refs: Any, cache: dict) -> list[str]:
    _objects(refs, "artifacts")
    issues = []
    for ref in refs:
        value = _text(ref.get("path"), "artifact.path")
        expected = _text(ref.get("sha256"), "artifact.sha256")
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise KitError("artifact.sha256 must be 64 lowercase hex characters")
        path = _artifact_path(root, profile, value)
        if not path.is_file():
            issues.append(f"missing_artifact:{value}")
        else:
            if path not in cache:
                cache[path] = _digest(path)
            if cache[path] != expected:
                issues.append(f"changed_artifact:{value}")
    return issues


RUN_STATUSES = {"passed", "proven", "failed", "counterexample", "inconclusive",
                "compile_error", "timeout", "infra_error", "running", "skipped", "unknown"}


def _validate_run(run: dict, plan: dict) -> None:
    if type(run.get("schema_version")) is not int or run["schema_version"] != 1:
        raise KitError("DV run schema_version must be 1")
    if run.get("project") != plan["project"]:
        raise KitError("DV run project does not match plan")
    for field in ("run_id", "requirement_id", "case_id", "configuration", "test", "tool_version"):
        _text(run.get(field), f"run.{field}")
    req = next((r for r in plan["requirements"] if r["id"] == run["requirement_id"]), None)
    if not req or run["configuration"] not in req["configurations"]:
        raise KitError(f"Unknown requirement/configuration in run {run['run_id']}")
    case = next((c for c in req["cases"] if c["id"] == run["case_id"]), None)
    if not case or run.get("method") != case["method"] or run["test"] != case["test"]:
        raise KitError(f"Case/method/test mismatch in run {run['run_id']}")
    if not isinstance(run.get("status"), str) or run["status"] not in RUN_STATUSES:
        raise KitError("Invalid run.status")
    if type(run.get("complete")) is not bool:
        raise KitError("run.complete must be boolean")
    command = run.get("command")
    if not isinstance(command, list) or not command:
        raise KitError("run.command must be a non-empty argv list")
    for argument in command:
        _text(argument, "run.command argument")
    _object(run.get("baseline"), "run.baseline")
    digest = _text(run["baseline"].get("input_digest"), "run.baseline.input_digest")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise KitError("run.baseline.input_digest must be a SHA-256 digest")
    if "source_revision" not in run["baseline"] or (
        run["baseline"]["source_revision"] is not None and not isinstance(run["baseline"]["source_revision"], str)
    ):
        raise KitError("run.baseline.source_revision must be a string or null")
    _objects(run.get("artifacts"), "run.artifacts")
    if run["method"] == "simulation" and (type(run.get("seed")) is not int or run["seed"] < 0):
        raise KitError("Simulation run.seed must be a non-negative integer")
    for field in ("checkers", "coverage"):
        items = _objects(run.get(field), f"run.{field}", empty=True)
        ids = [_text(item.get("id"), f"run.{field}.id") for item in items]
        _strings(ids, f"run.{field} IDs", empty=True)


def report(root: Path, profile: dict, plan_path: str, run_paths: list[str]) -> dict:
    plan = load_json(root, profile, plan_path)
    current = snapshot(root, profile, plan)
    runs = [load_json(root, profile, p) for p in run_paths]
    seen = set()
    for run in runs:
        _validate_run(run, plan)
        # A run/case pair is unique; one physical regression may cover many cases.
        key = (run["run_id"], run["requirement_id"], run["case_id"], run["configuration"])
        if key in seen:
            raise KitError(f"Duplicate run evidence: {key}")
        seen.add(key)
    rows = []
    cache: dict = {}
    for req in plan["requirements"]:
        for configuration in req["configurations"]:
            for case in req["cases"]:
                gaps = []
                if req["open_questions"]:
                    gaps.append("unresolved_questions")
                if req["open_bugs"]:
                    gaps.append("open_bugs")
                if not case["checkers"]:
                    gaps.append("missing_checker_mapping")
                if not case["coverage_targets"]:
                    gaps.append("missing_coverage_mapping")
                matching = [r for r in runs if r["requirement_id"] == req["id"]
                            and r["case_id"] == case["id"] and r["configuration"] == configuration]
                fresh = [r for r in matching if r["baseline"].get("input_digest") == current["input_digest"]
                         and r["baseline"].get("source_revision") == current["source_revision"]]
                stale = [r["run_id"] for r in matching if r not in fresh]
                accepted = []
                rejected = []
                blocking = []
                for run in fresh:
                    issues = _artifact_issues(root, profile, run["artifacts"], cache)
                    expected = "passed" if case["method"] == "simulation" else "proven"
                    if run["status"] != expected:
                        blocking.append(f"run_not_successful:{run['run_id']}:{run['status']}")
                    if run["complete"] is not True:
                        blocking.append(f"run_incomplete:{run['run_id']}")
                    for checker in case["checkers"]:
                        item = next((c for c in run["checkers"] if c["id"] == checker), {})
                        if item.get("active") is not True or item.get("status") != expected:
                            issues.append(f"checker_not_demonstrated:{checker}")
                        else:
                            issues.extend(_artifact_issues(root, profile, item.get("artifacts"), cache))
                        if case["require_negative_control"]:
                            control = _object(item.get("negative_control", {}), "negative_control")
                            if control.get("detected") is not True:
                                issues.append(f"missing_negative_control:{checker}")
                            else:
                                issues.extend(_artifact_issues(root, profile, control.get("artifacts"), cache))
                    for target in case["coverage_targets"]:
                        item = next((c for c in run["coverage"] if c["id"] == target), {})
                        if item.get("hit") is not True or item.get("complete") is not True:
                            issues.append(f"target_not_demonstrated:{target}")
                        else:
                            issues.extend(_artifact_issues(root, profile, item.get("artifacts"), cache))
                    if case["method"] == "formal":
                        proof = _object(run.get("formal", {}), "run.formal")
                        for field in ("assumptions_reviewed", "nonvacuous", "unbounded"):
                            if proof.get(field) is not True:
                                issues.append(f"formal_{field}_not_demonstrated")
                        if not isinstance(proof.get("scope"), str) or not proof["scope"].strip():
                            issues.append("formal_missing_scope")
                        if proof.get("artifacts"):
                            issues.extend(_artifact_issues(root, profile, proof["artifacts"], cache))
                        else:
                            issues.append("formal_missing_evidence")
                    if issues:
                        rejected.append({"run_id": run["run_id"], "issues": issues})
                    elif run["status"] == expected and run["complete"]:
                        accepted.append(run["run_id"])
                gaps.extend(blocking)
                if not fresh:
                    gaps.append("stale_evidence" if stale else "missing_run")
                elif not accepted:
                    gaps.append("incomplete_evidence")
                # Corrupt/missing artifacts cannot be hidden by another passing seed.
                if rejected:
                    gaps.append("invalid_or_incomplete_run_evidence")
                rows.append({"requirement_id": req["id"], "configuration": configuration,
                             "case_id": case["id"], "method": case["method"],
                             "status": "gaps" if gaps else "ready_for_review", "gaps": gaps,
                             "accepted_runs": accepted, "stale_runs": stale, "rejected_runs": rejected})
    ready = sum(row["status"] == "ready_for_review" for row in rows)
    return {"schema_version": 1, "kind": "dv-requirement-report", "project": plan["project"],
            "status": "ready_for_review" if ready == len(rows) else "gaps", "signoff": False,
            "baseline": {k: v for k, v in current.items() if k != "files"},
            "input_file_count": len(current["files"]),
            "summary": {"total": len(rows), "ready_for_review": ready, "gaps": len(rows) - ready},
            "rows": rows,
            "limitations": ["Only declared inputs and supplied run records are checked.",
                            "Artifact hashes verify integrity, not the truth of adapter-extracted claims.",
                            "Scope, checker semantics, assumptions and final signoff require engineering review."]}


def markdown_report(result: dict) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = [f"# DV evidence: {cell(result['project'])}", "", "Evidence readiness only; not signoff.", "",
             f"Input digest: {cell(result['baseline']['input_digest'])}",
             f"Source revision: {cell(result['baseline']['source_revision'] or 'unavailable')}", "",
             "| Requirement | Config | Case | Status | Gaps | Accepted runs | Stale runs |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    details = []
    for row in result["rows"]:
        values = [row["requirement_id"], row["configuration"], row["case_id"], row["status"],
                  ", ".join(row["gaps"]), ", ".join(row["accepted_runs"]), ", ".join(row["stale_runs"])]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
        for rejected in row["rejected_runs"]:
            details.append(cell(rejected["run_id"]) + ": " + cell(", ".join(rejected["issues"])))
    lines.extend(["", *details, "", *result["limitations"], ""])
    return "\n".join(lines)
