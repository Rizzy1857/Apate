from chronos.intelligence.artifact_policy import ArtifactPolicy

class FallbackProvider:
    """
    Provides degraded content when the Circuit Breaker is OPEN or when validation fails.
    This replaces hardcoded static templates inside the orchestrator, giving a clean
    boundary for future caching or procedural fallback strategies.
    """
    def __init__(self):
        pass

    def get_degraded_content(self, filename: str, policy: ArtifactPolicy) -> bytes:
        """
        Returns a minimal static template for the file class.
        The template must never look like an AI fallback to an attacker.
        """
        templates = {
            "config_file": b"# configuration file\n",
            "log_file": b"",
            "credential_file": b"",
            "history_file": b"",
            "notes_file": b"",
            "script_file": b"#!/bin/bash\n",
            "temp_file": b"",
        }
        return templates.get(policy.file_class, b"")
