"""
artifact_policy.py
------------------
Resolves the artifact policy for a file before generation occurs.
The AI fills a predefined role — it does not invent content from scratch.

Policy source: config/generation_policy.yaml (behavior)
Machine state: config/ubuntu.yaml via UbuntuProfile (state)

These are deliberately kept separate.
"""

import os
import random
import yaml
from typing import Any, Dict, Optional

_POLICY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "config", "generation_policy.yaml"
)

# File class inference — maps filename patterns and paths to a file class.
# Ordered: first match wins.
_FILE_CLASS_RULES = [
    # Credentials
    (lambda n, p: any(kw in n.lower() for kw in ("passwd", "shadow", "secret", "token", "key", ".env", "credential", "password")), "credential_file"),
    # SSH keys / authorized_keys
    (lambda n, p: "authorized_keys" in n or n.endswith(".pem") or n.endswith(".key"), "credential_file"),
    # Shell / interpreter history
    (lambda n, p: "history" in n.lower(), "history_file"),
    # Log files
    (lambda n, p: "/var/log/" in p or n.endswith(".log"), "log_file"),
    # Configs
    (lambda n, p: "/etc/" in p or n.endswith(".conf") or n.endswith(".cfg") or n.endswith(".ini"), "config_file"),
    # Scripts
    (lambda n, p: n.endswith(".sh") or n.endswith(".py") or n.endswith(".pl") or n.endswith(".rb"), "script_file"),
    # Notes / loose text
    (lambda n, p: any(kw in n.lower() for kw in ("note", "todo", "readme", "scratch", "draft")), "notes_file"),
    # Temp files
    (lambda n, p: "/tmp/" in p or n.endswith(".tmp") or n.endswith(".lock") or n.endswith(".pid"), "temp_file"),
]

_DEFAULT_CLASS = "config_file"


def infer_file_class(filename: str, path: str) -> str:
    """Infer the file class from filename and path. Returns a class key."""
    for predicate, cls in _FILE_CLASS_RULES:
        if predicate(filename, path):
            return cls
    return _DEFAULT_CLASS


class ArtifactPolicyEngine:
    """
    Resolves per-file artifact policy from generation_policy.yaml.

    Responsibilities:
    - Determine file class (credential_file, log_file, config_file, …)
    - Sample an artifact category from the class probability distribution
    - Expose hard constraints (max_lines, max_entries, validation_strictness)
    - Short-circuit: 'empty' category skips AI entirely

    This runs BEFORE generation, not after.
    """

    def __init__(self, policy_path: Optional[str] = None):
        path = os.path.abspath(policy_path or _POLICY_PATH)
        try:
            with open(path, "r") as f:
                raw = yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"[ArtifactPolicyEngine] WARNING: Policy not found at {path}. Using built-in defaults.")
            raw = {}

        self._artifact_policy: Dict[str, Any] = raw.get("artifact_policy", {})
        self._model_routing: Dict[str, str] = raw.get("model_routing", {})
        self._prewarm_priorities: list = raw.get("prewarm_priorities", [])
        self._quota: Dict[str, Any] = raw.get("inference_quota", {
            "max_generations_per_minute": 20,
            "quota_exhausted_behavior": "template",
        })

    def resolve(self, filename: str, path: str) -> "ArtifactPolicy":
        """
        Resolve the full artifact policy for a given file.
        The returned object describes what the AI should produce and how.
        """
        file_class = infer_file_class(filename, path)
        class_policy = self._artifact_policy.get(file_class, {})

        distribution: Dict[str, float] = class_policy.get("distribution", {"valid": 1.0})
        category = _sample_category(distribution)

        return ArtifactPolicy(
            file_class=file_class,
            category=category,
            max_lines=class_policy.get("max_lines", 80),
            max_entries=class_policy.get("max_entries", None),
            max_days=class_policy.get("max_days", None),
            validation_strictness=class_policy.get("validation_strictness", "medium"),
            regeneration=class_policy.get("regeneration", "static"),
            model=self._model_routing.get(file_class, self._model_routing.get("default", "llama3:8b")),
        )

    def quota_config(self) -> Dict[str, Any]:
        return self._quota

    def prewarm_priorities(self) -> list:
        return self._prewarm_priorities


class ArtifactPolicy:
    """
    Resolved policy for a single file. Passed to PromptBuilder and GenerationOrchestrator.
    """

    def __init__(
        self,
        file_class: str,
        category: str,
        max_lines: int,
        max_entries: Optional[int],
        max_days: Optional[int],
        validation_strictness: str,
        regeneration: str,
        model: str,
    ):
        self.file_class = file_class
        self.category = category            # e.g. "valid", "empty", "abandoned", "corrupted"
        self.max_lines = max_lines
        self.max_entries = max_entries
        self.max_days = max_days
        self.validation_strictness = validation_strictness
        self.regeneration = regeneration    # "static" | "dynamic"
        self.model = model

    @property
    def skip_generation(self) -> bool:
        """True when AI must not be called — return b'' directly."""
        return self.category in ("empty",)

    def __repr__(self) -> str:
        return (
            f"ArtifactPolicy(class={self.file_class!r}, category={self.category!r}, "
            f"model={self.model!r}, max_lines={self.max_lines}, skip={self.skip_generation})"
        )


def _sample_category(distribution: Dict[str, float]) -> str:
    """Weighted random sample from a probability distribution dict."""
    keys = list(distribution.keys())
    weights = [distribution[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]
