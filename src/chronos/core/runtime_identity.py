"""Fingerprint deployed inputs at process startup for session provenance."""
import hashlib
import json
import os
from pathlib import Path


def fingerprint_runtime(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    source, configuration = {}, {}
    for folder, output in (("src", source), ("config", configuration)):
        for directory, children, files in os.walk(root / folder):
            children[:] = sorted(name for name in children if name not in
                                 {"target", "__pycache__", ".git", ".pytest_cache"})
            for name in sorted(files):
                path = Path(directory) / name
                if path.is_symlink() or path.suffix in {".pyc", ".pyo"} or name == ".DS_Store":
                    continue
                output[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    requirements = root / "requirements.txt"
    if requirements.is_file():
        source["requirements.txt"] = hashlib.sha256(requirements.read_bytes()).hexdigest()
    configuration["runtime_modes"] = {
        key: os.environ.get(key, default) for key, default in (
            ("CHRONOS_INFERENCE_MODE", "deterministic"),
            ("CHRONOS_ARTIFACT_TREATMENT", "deterministic"),
            ("CHRONOS_PERSISTENT_RUNS", "0"),
            ("CHRONOS_WORKER_CPU_SECONDS", "300"))
    }
    digest = lambda mapping: hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()
    return {"APATE_SOURCE_REVISION": "runtime-sha256:" + digest(source),
            "APATE_CONFIGURATION_DIGEST": digest(configuration),
            "APATE_PROFILE_DIGEST": configuration.get("config/ubuntu.yaml", "")}
