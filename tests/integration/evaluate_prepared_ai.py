"""Run the frozen prepared-AI treatment against local Ollama.

This is an opt-in research harness, not part of the default test suite. It never
uses participant data or retained evidence. Each trial starts from the same
profile/reference time and performs at most two model attempts, matching the
production preparation policy. Every attempt and rejection is retained.
"""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time

from chronos.intelligence.artifact_policy import ArtifactPolicy, ArtifactPolicyEngine
from chronos.intelligence.inference import InferenceRuntime, ModelUnreachableError
from chronos.intelligence.prepared_artifacts import bundle_spec, model_identities
from chronos.intelligence.prompt_builder import PromptBuilder
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.validator import SemanticValidator


@dataclass
class Attempt:
    attempt: int
    elapsed_seconds: float
    generation_seconds: float
    validation_seconds: float
    accepted: bool
    reason: str
    response_bytes: int
    response_sha256: str | None
    response_file: str | None


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def latency_summary(values):
    return {
        "median": statistics.median(values) if values else None,
        "p95_nearest_rank": percentile(values, 0.95),
        "maximum": max(values) if values else None,
    }


def summarize(rows):
    accepted = sum(1 for row in rows if row["accepted"])
    return {
        "trials": len(rows),
        "accepted": accepted,
        "rejected_or_failed": len(rows) - accepted,
        "acceptance_rate": accepted / len(rows) if rows else None,
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


def source_revision():
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
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
    return {
        "commit": revision,
        "working_tree_dirty": dirty,
        "evaluation_source_sha256": snapshot.hexdigest(),
        "evaluation_source_files": len(files),
    }


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


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    artifacts_dir = output / "accepted_artifacts"
    artifacts_dir.mkdir()
    attempts_dir = output / "attempt_artifacts"
    attempts_dir.mkdir()

    profile = UbuntuProfile()
    machine = profile.build_machine_state()
    machine["created_at"] = str(args.reference_epoch)
    engine = ArtifactPolicyEngine()
    runtime = InferenceRuntime(host=args.ollama_host)
    builder = PromptBuilder()
    validator = SemanticValidator()
    paths = [
        entry["path"]
        for entry in profile.filesystem_manifest["entries"]
        if entry.get("class") == "ai_backed"
    ]
    policies = {path: valid_policy(engine, path, machine) for path in paths}
    identities = model_identities(runtime, [policy.model for policy in policies.values()])

    rows = []
    for path in paths:
        policy = policies[path]
        prompt = builder.build(Path(path).name, path, machine, policy)
        system_prompt = builder.build_system_prompt(machine)
        for trial in range(1, args.trials + 1):
            attempts = []
            accepted_content = None
            trial_persistence_seconds = 0.0
            trial_started = time.monotonic()
            for attempt_number in range(1, 3):
                started = time.monotonic()
                try:
                    generation_started = time.monotonic()
                    content = runtime.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        model=policy.model,
                        max_tokens=min(1200, max(512, (policy.max_lines or 80) * 10)),
                        timeout=args.timeout,
                    )
                    generation_seconds = time.monotonic() - generation_started
                    validation_started = time.monotonic()
                    validation = validator.validate(
                        content, policy, {**machine, "artifact_path": path}
                    )
                    validation_seconds = time.monotonic() - validation_started
                    attempt_elapsed = generation_seconds + validation_seconds
                    encoded = content.encode("utf-8")
                    response_file = (
                        f"{path.strip('/').replace('/', '__')}"
                        f"__trial_{trial:02d}__attempt_{attempt_number}.txt"
                    )
                    persistence_started = time.monotonic()
                    (attempts_dir / response_file).write_bytes(encoded)
                    trial_persistence_seconds += (
                        time.monotonic() - persistence_started
                    )
                    attempts.append(
                        Attempt(
                            attempt=attempt_number,
                            elapsed_seconds=attempt_elapsed,
                            generation_seconds=generation_seconds,
                            validation_seconds=validation_seconds,
                            accepted=validation.accepted,
                            reason=validation.reason,
                            response_bytes=len(encoded),
                            response_sha256=hashlib.sha256(encoded).hexdigest(),
                            response_file=response_file,
                        )
                    )
                    if validation.accepted:
                        accepted_content = encoded
                        break
                except ModelUnreachableError as exc:
                    attempts.append(
                        Attempt(
                            attempt=attempt_number,
                            elapsed_seconds=time.monotonic() - started,
                            generation_seconds=time.monotonic() - started,
                            validation_seconds=0.0,
                            accepted=False,
                            reason=f"inference:{exc.reason}",
                            response_bytes=0,
                            response_sha256=None,
                            response_file=None,
                        )
                    )

            artifact_file = None
            persistence_started = time.monotonic()
            if accepted_content is not None:
                artifact_file = (
                    f"{path.strip('/').replace('/', '__')}__trial_{trial:02d}.txt"
                )
                (artifacts_dir / artifact_file).write_bytes(accepted_content)
            trial_persistence_seconds += time.monotonic() - persistence_started
            row = {
                "path": path,
                "file_class": policy.file_class,
                "model": policy.model,
                "model_digest": identities[policy.model],
                "trial": trial,
                "accepted": accepted_content is not None,
                "compute_seconds": sum(
                    attempt.elapsed_seconds for attempt in attempts
                ),
                "persistence_seconds": trial_persistence_seconds,
                "elapsed_seconds": time.monotonic() - trial_started,
                "attempts": [asdict(attempt) for attempt in attempts],
                "artifact_file": artifact_file,
            }
            rows.append(row)
            print(json.dumps(row), flush=True)
            (output / "trials.partial.json").write_text(
                json.dumps(rows, indent=2, sort_keys=True)
            )

    by_path = {
        path: summarize([row for row in rows if row["path"] == path]) for path in paths
    }
    report = {
        "schema_version": 2,
        "treatment": "prepared_ai_valid_only",
        "independence_unit": "one uncached generation trial; up to two attempts",
        "reference_epoch": args.reference_epoch,
        "source": source_revision(),
        "bundle_spec": bundle_spec(profile),
        "model_identities": identities,
        "runtime": {
            "ollama_host": args.ollama_host,
            "timeout_seconds_per_attempt": args.timeout,
            "temperature": 0.1,
            "model_seed": None,
        },
        "limitations": [
            "No independent human plausibility rating is included.",
            "Ollama/model execution may be nondeterministic because no model seed is set.",
            "Acceptance means the current automated validator passed, not universal correctness.",
            "Attempt bodies are synthetic but may still be unsuitable for public sharing without review.",
        ],
        "summary": {"overall": summarize(rows), "by_path": by_path},
        "trials": rows,
    }
    (output / "evaluation.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    (output / "complete.json").write_text(
        json.dumps(
            {
                "artifact_type": "prepared_ai_evaluation",
                "schema_version": 2,
                "trials": len(rows),
                "accepted": report["summary"]["overall"]["accepted"],
                "evaluation_sha256": hashlib.sha256(
                    (output / "evaluation.json").read_bytes()
                ).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    (output / "trials.partial.json").unlink(missing_ok=True)
    print(json.dumps(report["summary"], indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--reference-epoch", type=float, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--ollama-host", default=os.environ.get("OLLAMA_HOST", "127.0.0.1"))
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    run(args)


if __name__ == "__main__":
    main()
