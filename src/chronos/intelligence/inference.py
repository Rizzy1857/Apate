"""
inference.py
------------
Local inference runtime targeting the Ollama container on chronos-net.

Model routing is defined in config/generation_policy.yaml under `model_routing`,
keyed by Ubuntu file class (config_file, log_file, credential_file, …).
The ModelRouter class here is a thin resolver — it reads from the policy,
not from hardcoded rules, so adding a new file class never requires a code change.

This module has no concept of cloud LLM providers. The stack is air-gapped.
"""

import os
import requests
from typing import Optional


class InferenceRuntime:
    """Local inference runtime targeting Ollama on chronos-net."""

    def __init__(self, host: Optional[str] = None):
        self.host = host or os.environ.get("OLLAMA_HOST", "localhost")
        self.base_url = f"http://{self.host}:11434/api/generate"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "llama3:8b",
        max_tokens: int = 1000,
    ) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.RequestException as e:
            # The orchestrator's circuit breaker handles repeated failures.
            # Log and return empty — never raise so FUSE doesn't see a Python exception.
            print(f"[InferenceRuntime] Ollama unreachable ({self.host}): {e}")
            return ""

    def health_check(self) -> bool:
        """Returns True if Ollama is reachable. Used by circuit breaker."""
        try:
            response = requests.get(
                f"http://{self.host}:11434/api/tags", timeout=5.0
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


def get_runtime() -> InferenceRuntime:
    """Factory — always returns local Ollama runtime. No cloud providers."""
    return InferenceRuntime()
