"""Paired skill behavior evaluations over explicitly collected model outputs."""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from .core import KitError
from .dv import _object, _objects, _strings, _text
from .experiment import artifact, digest, integer, load, metric, parse_json, project, scope_snapshot, sha, unique

ARMS = ("baseline", "candidate")
METRICS = ("tokens", "duration_seconds", "tool_calls")


def validate_suite(suite: dict, profile: dict) -> None:
    project(suite, profile)
    _text(suite.get("id"), "suite.id")
    _strings(suite.get("inputs"), "inputs")
    integer(suite.get("repetitions"), "repetitions", 1, 100)
    arms = _object(suite.get("arms"), "arms")
    if set(arms) != set(ARMS):
        raise KitError("arms must contain baseline and candidate")
    for arm in ARMS:
        _text(_object(arms[arm], arm).get("label"), f"{arm}.label")
        _strings(arms[arm].get("skill_inputs"), f"{arm}.skill_inputs", empty=True)
    cases = _objects(suite.get("cases"), "cases")
    ids = []
    for case in cases:
        ids.append(_text(case.get("id"), "case.id"))
        _text(case.get("prompt"), "case.prompt")
        assertion_ids = []
        for assertion in _objects(case.get("assertions"), "assertions"):
            assertion_ids.append(_text(assertion.get("id"), "assertion.id"))
            _text(assertion.get("artifact"), "assertion.artifact")
            operator = assertion.get("operator")
            if operator == "json_equals":
                pointer = assertion.get("pointer")
                if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
                    raise KitError("JSON pointer must be empty or start with /")
                for component in pointer.split("/"):
                    if any(component[i:i + 2] not in ("~0", "~1") for i, ch in enumerate(component) if ch == "~"):
                        raise KitError("Invalid JSON pointer escape")
                if "expected" not in assertion:
                    raise KitError("json_equals requires expected")
            elif operator in ("text_contains", "text_not_contains"):
                _text(assertion.get("expected"), "assertion.expected")
            else:
                raise KitError("Unsupported assertion operator")
        unique(assertion_ids, "assertion IDs")
    unique(ids, "case IDs")
    if len(cases) * suite["repetitions"] > 10000:
        raise KitError("Suite exceeds 10000 evaluation pairs")


def snapshot(root: Path, profile: dict, suite: dict) -> dict:
    validate_suite(suite, profile)
    return {"suite_digest": digest(suite),
            "input_digest": scope_snapshot(root, profile, suite["inputs"])["input_digest"],
            "skill_digests": {arm: scope_snapshot(root, profile, suite["arms"][arm]["skill_inputs"])["input_digest"]
                              for arm in ARMS}}


def _pointer(value: Any, pointer: str) -> Any:
    if not pointer:
        return value
    for component in pointer[1:].split("/"):
        if any(component[i:i + 2] not in ("~0", "~1") for i, ch in enumerate(component) if ch == "~"):
            raise KitError("Invalid JSON pointer escape")
        key = component.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[key]
        elif isinstance(value, list) and key.isdigit() and (key == "0" or not key.startswith("0")):
            value = value[int(key)]
        else:
            raise KeyError(key)
    return value


def _grade(root: Path, profile: dict, case: dict, run: dict) -> dict:
    gaps = []
    outputs = _object(run.get("outputs"), "run.outputs")
    if "transcript" not in outputs:
        gaps.append("missing_transcript")
    contents = {}
    # Validate every supplied output, not only those used by an assertion.
    for name, ref in outputs.items():
        issues, data = artifact(root, profile, ref, bounded=True)
        gaps.extend(issues)
        if data is not None:
            contents[name] = data
    verdicts = []
    for assertion in case["assertions"]:
        data = contents.get(assertion["artifact"])
        passed = False
        reason = "assertion_failed"
        if data is None:
            # Not producing a requested output is a quality failure. A lost or
            # corrupt declared artifact remains an integrity gap above.
            reason = "output_not_produced" if assertion["artifact"] not in outputs else "artifact_unavailable"
        else:
            try:
                if assertion["operator"] == "json_equals":
                    actual = _pointer(parse_json(data), assertion["pointer"])
                    passed = digest(actual) == digest(assertion["expected"])
                else:
                    present = assertion["expected"] in data.decode("utf-8")
                    passed = present if assertion["operator"] == "text_contains" else not present
            except (KeyError, IndexError, UnicodeError, KitError):
                reason = "invalid_output_or_missing_value"
        verdicts.append({"id": assertion["id"], "passed": passed,
                         "artifact": assertion["artifact"], "reason": "matched" if passed else reason})
    if run["status"] != "completed":
        gaps.append(f"execution_status:{run['status']}")
    return {"run_id": run["run_id"], "model": run["model"], "environment_id": run["environment_id"],
            "settings_digest": run["settings_digest"], "outputs": outputs,
            "passed": not gaps and all(v["passed"] for v in verdicts),
            "assertions": verdicts, "gaps": gaps}


def _stats(values: list[float | int]) -> dict:
    return {"count": len(values), "mean": statistics.mean(values) if values else None,
            "stdev": statistics.stdev(values) if len(values) > 1 else None}


def report(root: Path, profile: dict, suite_path: str, run_paths: list[str]) -> dict:
    suite = load(root, profile, suite_path)
    current = snapshot(root, profile, suite)
    cases = {c["id"]: c for c in suite["cases"]}
    runs = {}
    run_ids = []
    for path in run_paths:
        run = load(root, profile, path)
        project(run, profile)
        for field in ("suite_id", "case_id", "arm"):
            _text(run.get(field), f"run.{field}")
        if run.get("suite_id") != suite["id"] or run.get("case_id") not in cases or run.get("arm") not in ARMS:
            raise KitError("Unknown suite, case or arm in evaluation run")
        repetition = integer(run.get("repetition"), "run.repetition", 1, suite["repetitions"])
        key = (run["case_id"], repetition, run["arm"])
        if key in runs:
            raise KitError("Duplicate case/repetition/arm")
        run_ids.append(_text(run.get("run_id"), "run.run_id"))
        if run.get("status") not in ("completed", "failed", "timeout", "infra_error"):
            raise KitError("Invalid evaluation run.status")
        for field in ("model", "environment_id"):
            _text(run.get(field), f"run.{field}")
        for field in ("suite_digest", "input_digest", "skill_digest", "settings_digest"):
            sha(run.get(field), f"run.{field}")
        metrics = _object(run.get("metrics"), "run.metrics")
        for name in METRICS:
            metric(metrics.get(name), name)
        runs[key] = run
    unique(run_ids, "run IDs")
    pairs = []
    for case_id, case in cases.items():
        for repetition in range(1, suite["repetitions"] + 1):
            pair = {"case_id": case_id, "repetition": repetition, "arms": {}, "gaps": []}
            actual = {}
            for arm in ARMS:
                run = runs.get((case_id, repetition, arm))
                if run is None:
                    pair["gaps"].append(f"missing_run:{arm}")
                    continue
                actual[arm] = run
                for field in ("suite_digest", "input_digest"):
                    if run[field] != current[field]:
                        pair["gaps"].append(f"stale_{field}:{arm}")
                if run["skill_digest"] != current["skill_digests"][arm]:
                    pair["gaps"].append(f"stale_skill_digest:{arm}")
                pair["arms"][arm] = _grade(root, profile, case, run)
                pair["gaps"].extend(f"{arm}:{gap}" for gap in pair["arms"][arm]["gaps"])
            if len(actual) == 2:
                for field in ("model", "settings_digest", "environment_id"):
                    if actual["baseline"][field] != actual["candidate"][field]:
                        pair["gaps"].append(f"unpaired_{field}")
            pair["comparable"] = not pair["gaps"]
            pair["metrics"] = {}
            if pair["comparable"]:
                for name in METRICS:
                    before = actual["baseline"]["metrics"].get(name)
                    after = actual["candidate"]["metrics"].get(name)
                    pair["metrics"][name] = {"baseline": before, "candidate": after,
                                              "delta": after - before if before is not None and after is not None else None}
            pairs.append(pair)
    comparable = [p for p in pairs if p["comparable"]]
    summary = {"expected_pairs": len(pairs), "comparable_pairs": len(comparable),
               "gap_pairs": len(pairs) - len(comparable)}
    for arm in ARMS:
        summary[f"{arm}_pass_rate"] = statistics.mean(p["arms"][arm]["passed"] for p in comparable) if comparable else None
    delta = None if not comparable else summary["candidate_pass_rate"] - summary["baseline_pass_rate"]
    return {"schema_version": 1, "kind": "skill-evaluation", "suite_id": suite["id"],
            "status": "complete" if len(comparable) == len(pairs) else "gaps",
            "summary": summary, "pass_rate_delta": delta,
            "metric_deltas": {name: _stats([p["metrics"][name]["delta"] for p in comparable
                                            if p["metrics"][name]["delta"] is not None]) for name in METRICS},
            "pairs": pairs, "snapshot": current,
            "limitations": ["Collector declarations are not independently observed execution.",
                            "JSON/text assertions verify supplied outputs; task correctness and trace completeness need review.",
                            "Missing metrics remain unknown. Paired samples do not establish statistical significance.",
                            "A complete comparison can show regressions; completion is not a quality approval."]}
