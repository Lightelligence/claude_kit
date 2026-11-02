"""Evidence-only validation of one fix against pinned before/after inputs."""
from __future__ import annotations

from pathlib import Path

from .core import KitError
from .dv import _object, _objects, _strings, _text
from .experiment import artifacts, baseline, load, project, scope_snapshot, unique

KINDS = {"reproducer", "variant", "control", "regression"}


def validate_plan(plan: dict, profile: dict) -> None:
    project(plan, profile)
    for field in ("id", "root_cause"):
        _text(plan.get(field), field)
    _strings(plan.get("inputs"), "inputs")
    before = baseline(plan.get("base"))
    after = baseline(plan.get("patched"))
    if before["input_digest"] == after["input_digest"]:
        raise KitError("Base and patched input digests must differ")
    checks = _objects(plan.get("checks"), "checks")
    ids, kinds = [], set()
    for check in checks:
        ids.append(_text(check.get("id"), "check.id"))
        if check.get("kind") not in KINDS:
            raise KitError("Invalid fix check.kind")
        kinds.add(check["kind"])
        for field in ("test", "configuration"):
            _text(check.get(field), f"check.{field}")
        if "seed" not in check or (check["seed"] is not None and (type(check["seed"]) is not int or check["seed"] < 0)):
            raise KitError("check.seed must be an integer or null")
        if check["kind"] in ("reproducer", "variant"):
            _text(check.get("failure_signature"), "check.failure_signature")
    unique(ids, "check IDs")
    if not {"reproducer", "control", "regression"} <= kinds:
        raise KitError("Fix plan requires reproducer, control and regression checks")
    search = _object(plan.get("variant_review"), "variant_review")
    if search.get("status") not in ("pending", "reviewed"):
        raise KitError("variant_review.status must be pending or reviewed")
    _text(search.get("rationale"), "variant_review.rationale")
    if search["status"] == "reviewed":
        _text(search.get("reviewer"), "variant_review.reviewer")
    _objects(search.get("artifacts"), "variant_review.artifacts", empty=True)


def report(root: Path, profile: dict, plan_path: str, run_paths: list[str]) -> dict:
    plan = load(root, profile, plan_path)
    validate_plan(plan, profile)
    current = scope_snapshot(root, profile, plan["inputs"])
    global_gaps = []
    for field in ("input_digest", "source_revision"):
        if current[field] != plan["patched"][field]:
            global_gaps.append(f"stale_patched_{field}")
    review = plan["variant_review"]
    if review["status"] != "reviewed" or not review["artifacts"]:
        global_gaps.append("variant_review_required")
    elif review["artifacts"]:
        global_gaps.extend(artifacts(root, profile, review["artifacts"]))
    checks = {c["id"]: c for c in plan["checks"]}
    runs, ids = {}, []
    for path in run_paths:
        run = load(root, profile, path)
        project(run, profile)
        for field in ("fix_id", "check_id", "side"):
            _text(run.get(field), f"run.{field}")
        if run.get("fix_id") != plan["id"] or run.get("check_id") not in checks or run.get("side") not in ("base", "patched"):
            raise KitError("Unknown fix, check or side in validation run")
        key = (run["check_id"], run["side"])
        if key in runs:
            raise KitError("Duplicate check/side run; select one explicit paired review set")
        ids.append(_text(run.get("run_id"), "run.run_id"))
        for field in ("test", "configuration", "tool_version"):
            _text(run.get(field), f"run.{field}")
        if not isinstance(run.get("command"), list) or not run["command"]:
            raise KitError("run.command must be a non-empty argv list")
        for argument in run["command"]:
            _text(argument, "run.command argument")
        if "seed" not in run or (run["seed"] is not None and (type(run["seed"]) is not int or run["seed"] < 0)):
            raise KitError("run.seed must be a non-negative integer or null")
        baseline(run.get("baseline"))
        if type(run.get("complete")) is not bool:
            raise KitError("run.complete must be boolean")
        if run.get("status") not in ("passed", "failed", "timeout", "infra_error", "compile_error", "inconclusive", "skipped"):
            raise KitError("Invalid fix run.status")
        runs[key] = run
    unique(ids, "run IDs")
    rows = []
    for check_id, check in checks.items():
        gaps = []
        sides = {}
        for side in ("base", "patched"):
            run = runs.get((check_id, side))
            if run is None:
                gaps.append(f"missing_run:{side}")
                continue
            sides[side] = run["run_id"]
            for field in ("test", "configuration", "seed"):
                if field not in run or run[field] != check[field]:
                    gaps.append(f"mismatched_{field}:{side}")
            for field in ("input_digest", "source_revision"):
                if run["baseline"][field] != plan[side][field]:
                    gaps.append(f"mismatched_baseline_{field}:{side}")
            expected = "failed" if side == "base" and check["kind"] in ("reproducer", "variant") else "passed"
            if run["status"] != expected or not run["complete"]:
                gaps.append(f"unexpected_result:{side}")
            if expected == "failed" and run.get("failure_signature") != check["failure_signature"]:
                gaps.append(f"wrong_failure_signature:{side}")
            gaps.extend(artifacts(root, profile, run.get("artifacts")))
        if len(sides) == 2 and runs[(check_id, "base")]["tool_version"] != runs[(check_id, "patched")]["tool_version"]:
            gaps.append("unpaired_tool_version")
        rows.append({"id": check_id, "kind": check["kind"], "runs": sides, "gaps": gaps,
                     "status": "gaps" if gaps else "ready_for_review"})
    ready = not global_gaps and all(row["status"] == "ready_for_review" for row in rows)
    return {"schema_version": 1, "kind": "fix-validation", "fix_id": plan["id"],
            "status": "ready_for_review" if ready else "gaps", "signoff": False,
            "summary": {"checks": len(rows), "ready_for_review": sum(r["status"] == "ready_for_review" for r in rows)},
            "gaps": global_gaps, "rows": rows,
            "limitations": ["No checks are executed. The collector owns failure signatures and result extraction.",
                            "Base evidence is checked against the declared pinned baseline, not a reconstructed checkout.",
                            "Variant review is a recorded engineering judgment, not a proof that no variants exist.",
                            "Only the explicitly supplied review set is checked; omitted runs cannot be discovered."]}
