"""Measure the frozen deterministic baseline for prepared-AI comparison."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

from chronos.intelligence.artifact_policy import ArtifactPolicy, ArtifactPolicyEngine
from chronos.intelligence.fallback import FallbackProvider
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.validator import SemanticValidator


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)] if ordered else None


def valid_policy(engine, path, machine):
    resolved = engine.resolve(Path(path).name, path, machine)
    return ArtifactPolicy(
        file_class=resolved.file_class,
        category="valid",
        max_lines=resolved.max_lines,
        max_entries=resolved.max_entries,
        max_days=resolved.max_days,
        validation_strictness=resolved.validation_strictness,
        regeneration=resolved.regeneration,
        model=resolved.model,
        manifest_class=resolved.manifest_class,
    )


def latency_summary(values):
    return {
        "median": statistics.median(values),
        "p95_nearest_rank": percentile(values, 0.95),
        "maximum": max(values),
    }


def summarize(rows):
    accepted = sum(row["accepted"] for row in rows)
    return {
        "trials": len(rows),
        "accepted": accepted,
        "rejected_or_failed": len(rows) - accepted,
        "acceptance_rate": accepted / len(rows),
        "unique_accepted_outputs": len(
            {row["response_sha256"] for row in rows if row["accepted"]}
        ),
        "compute_latency_seconds": latency_summary(
            [row["compute_seconds"] for row in rows]
        ),
        "persistence_latency_seconds": latency_summary(
            [row["persistence_seconds"] for row in rows]
        ),
        "total_latency_seconds": latency_summary(
            [row["elapsed_seconds"] for row in rows]
        ),
    }


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    artifact_dir = output / "artifacts"
    artifact_dir.mkdir()
    profile = UbuntuProfile()
    machine = profile.build_machine_state()
    machine["created_at"] = str(args.reference_epoch)
    engine = ArtifactPolicyEngine()
    provider = FallbackProvider()
    validator = SemanticValidator()
    paths = [
        entry["path"]
        for entry in profile.filesystem_manifest["entries"]
        if entry.get("class") == "ai_backed"
    ]
    rows = []
    for path in paths:
        policy = valid_policy(engine, path, machine)
        for trial in range(1, args.trials + 1):
            trial_started = time.perf_counter_ns()
            render_started = time.perf_counter_ns()
            content = provider.get_degraded_content(
                Path(path).name, policy, path, machine
            )
            render_seconds = (
                time.perf_counter_ns() - render_started
            ) / 1_000_000_000
            validation_started = time.perf_counter_ns()
            result = validator.validate(
                content.decode("utf-8"), policy, {**machine, "artifact_path": path}
            )
            validation_seconds = (
                time.perf_counter_ns() - validation_started
            ) / 1_000_000_000
            persistence_started = time.perf_counter_ns()
            artifact_file = None
            if trial == 1:
                artifact_file = path.strip("/").replace("/", "__") + ".txt"
                (artifact_dir / artifact_file).write_bytes(content)
            persistence_seconds = (
                time.perf_counter_ns() - persistence_started
            ) / 1_000_000_000
            rows.append(
                {
                    "path": path,
                    "file_class": policy.file_class,
                    "trial": trial,
                    "accepted": result.accepted,
                    "reason": result.reason,
                    "render_seconds": render_seconds,
                    "validation_seconds": validation_seconds,
                    "compute_seconds": render_seconds + validation_seconds,
                    "persistence_seconds": persistence_seconds,
                    "elapsed_seconds": (
                        time.perf_counter_ns() - trial_started
                    ) / 1_000_000_000,
                    "response_bytes": len(content),
                    "response_sha256": hashlib.sha256(content).hexdigest(),
                }
            )

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    roots = [Path("src"), Path("config")]
    files = sorted(
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and "target" not in path.parts
        and path.suffix != ".pyc"
    ) + [Path(__file__)]
    snapshot = hashlib.sha256()
    for path in files:
        snapshot.update(str(path).encode() + b"\0")
        snapshot.update(hashlib.sha256(path.read_bytes()).digest())
    report = {
        "schema_version": 2,
        "treatment": "deterministic_valid_only",
        "reference_epoch": args.reference_epoch,
        "source": {
            "commit": revision,
            "working_tree_dirty": dirty,
            "evaluation_source_sha256": snapshot.hexdigest(),
            "evaluation_source_files": len(files),
        },
        "runtime": {"model": "deterministic-none", "cache": "disabled"},
        "limitations": [
            "Repeated renders are timing repetitions, not independent stochastic samples.",
            "Automated validator acceptance is not an independent plausibility rating.",
            "Sub-millisecond timings are sensitive to instrumentation and host scheduling.",
        ],
        "summary": {
            "overall": summarize(rows),
            "by_path": {
                path: summarize([row for row in rows if row["path"] == path])
                for path in paths
            },
        },
        "trials": rows,
    }
    evaluation = output / "evaluation.json"
    evaluation.write_text(json.dumps(report, indent=2, sort_keys=True))
    (output / "complete.json").write_text(
        json.dumps(
            {
                "artifact_type": "deterministic_evaluation",
                "schema_version": 2,
                "trials": len(rows),
                "accepted": report["summary"]["overall"]["accepted"],
                "evaluation_sha256": hashlib.sha256(evaluation.read_bytes()).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(json.dumps(report["summary"], indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--reference-epoch", type=float, required=True)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    run(args)


if __name__ == "__main__":
    main()
