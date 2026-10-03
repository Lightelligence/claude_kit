"""Compare one saved core.py baseline with current code; emits JSON, no EDA.

Usage: python tests/benchmark_core_runtime.py --baseline /private/core.py
The fixture, resource tree, git facts and requests are identical. Timings measure
warm local Python resolution; output byte counts are not model token usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from claude_kit import core


def load_baseline(path: Path):
    spec = importlib.util.spec_from_file_location("core_baseline", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load baseline")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.resource_root = core.resource_root
    return module


def measure(module, operation: str, iterations: int):
    fixture = ROOT / "tests" / "fixtures" / "minimal_project"
    profile_path, profile = core.load_profile(fixture)
    resources = core.resource_root()
    reads = 0
    original_open = Path.open

    def traced_open(path, *args, **kwargs):
        nonlocal reads
        if path.is_relative_to(resources):
            reads += 1
        return original_open(path, *args, **kwargs)

    def invoke():
        if operation == "plan":
            return module.resolve_plan(
                fixture, profile_path, profile, "rtl-change", None,
                ["protocols.apb", "protocols.axi4"], "bounded RTL module update",
            )
        return module.resolve_context(
            fixture, profile_path, profile,
            ["rtl-architect", "rtl-designer", "reviewer", "evidence-reviewer"],
            ["protocols.apb", "protocols.axi4"], "bounded RTL module update",
            ["rtl-design", "rtl-dv-evidence"],
        )

    with patch.object(module, "_git_facts", return_value={"source_revision": "fixture", "worktree_dirty": False}):
        with patch.object(Path, "open", traced_open):
            result = invoke()
        invoke()  # Warm filesystem and Python paths before timing.
        samples = []
        for _ in range(iterations):
            start = time.perf_counter()
            invoke()
            samples.append((time.perf_counter() - start) * 1000)
    return result, {"resource_reads": reads, "median_ms": statistics.median(samples), "iterations": iterations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    if args.iterations < 3:
        parser.error("iterations must be at least 3")
    baseline = load_baseline(args.baseline)
    report = {"measurement": "warm local resolution, identical fixture; bytes are not tokens"}
    for operation in ("plan", "context"):
        timings = {"before": [], "after": []}
        stats = {}
        for index in range(args.iterations):
            outcomes = {}
            order = [("before", baseline), ("after", core)]
            if index % 2:
                order.reverse()
            for label, module in order:
                outcomes[label], stats[label] = measure(module, operation, 1)
                timings[label].append(stats[label]["median_ms"])
            if outcomes["before"] != outcomes["after"]:
                raise AssertionError(f"{operation} result changed for the comparison fixture")
        for label in stats:
            stats[label].update(median_ms=statistics.median(timings[label]), iterations=args.iterations)
        before_stats, after_stats = stats["before"], stats["after"]
        report[operation] = {"before": before_stats, "after": after_stats, "identical_response": True}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        profile = {"build": {"commands": {"large": {"argv": [
            sys.executable, "-c", "import sys; sys.stdout.write('A'*600000); sys.stderr.write('B'*600000)",
        ]}}}}
        before = baseline.run_project_command(root, profile, "large")
        after = core.run_project_command(root, profile, "large")
        for stream in ("stdout", "stderr"):
            path = root / after["output_artifacts"][stream]["path"]
            if path.read_bytes() != before[stream].encode("utf-8"):
                raise AssertionError("Full output artifact differs")
        report["large_output"] = {
            "before_response_bytes": len(json.dumps(before).encode()),
            "after_response_bytes": len(json.dumps(after).encode()),
            "complete_stream_bytes": {stream: after["output_artifacts"][stream]["bytes"] for stream in ("stdout", "stderr")},
            "status_and_returncode_preserved": (before["status"], before["returncode"]) == (after["status"], after["returncode"]),
            "identical_complete_artifacts": True,
        }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
