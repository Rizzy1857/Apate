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
import time
import random
import threading
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

class BreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

@dataclass
class ModelHealth:
    state: BreakerState = BreakerState.CLOSED
    failures: int = 0
    successes: int = 0
    next_retry: float = 0.0
    last_success: float = 0.0
    last_failure: float = 0.0
    average_latency: float = 0.0

class ModelUnreachableError(Exception):
    """Raised when the AI model infrastructure is unavailable (e.g. connection refused or timeout)."""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, base_backoff: float = 10.0, max_backoff: float = 300.0):
        self.failure_threshold = failure_threshold
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.models: Dict[str, ModelHealth] = {}
        self._lock = threading.Lock()
        
    def _get_health(self, model: str) -> ModelHealth:
        if model not in self.models:
            self.models[model] = ModelHealth()
        return self.models[model]

    def can_execute(self, model: str) -> bool:
        health = self._get_health(model)
        
        if health.state == BreakerState.CLOSED:
            return True
            
        current_time = time.time()
        
        if health.state == BreakerState.OPEN:
            if current_time >= health.next_retry:
                with self._lock:
                    # Double-check lock
                    if health.state == BreakerState.OPEN and current_time >= health.next_retry:
                        health.state = BreakerState.HALF_OPEN
                        return True # Let one probe through
                return False # Other threads returning instantly while HALF_OPEN probe is in flight
            return False
            
        if health.state == BreakerState.HALF_OPEN:
            # Only the first thread that transitioned to HALF_OPEN should have returned True
            return False
            
        return False

    def record_success(self, model: str, latency: float = 0.0):
        health = self._get_health(model)
        health.successes += 1
        health.failures = 0
        health.state = BreakerState.CLOSED
        health.last_success = time.time()
        # Simple exponential moving average
        if health.average_latency == 0:
            health.average_latency = latency
        else:
            health.average_latency = (health.average_latency * 0.9) + (latency * 0.1)

    def record_failure(self, model: str):
        health = self._get_health(model)
        health.failures += 1
        health.last_failure = time.time()
        
        if health.state == BreakerState.HALF_OPEN or health.failures >= self.failure_threshold:
            health.state = BreakerState.OPEN
            
            # Exponential backoff: base * 2^(failures - threshold)
            exponent = max(0, health.failures - self.failure_threshold)
            backoff = min(self.max_backoff, self.base_backoff * (2 ** exponent))
            
            # Apply ±20% jitter
            jitter = random.uniform(0.8, 1.2)
            health.next_retry = time.time() + (backoff * jitter)


class InferenceRuntime:
    """Local inference runtime targeting Ollama on chronos-net."""

    def __init__(self, host: Optional[str] = None):
        self.host = host or os.environ.get("OLLAMA_HOST", "localhost")
        self.base_url = f"http://{self.host}:11434/api/generate"
        self.circuit_breaker = CircuitBreaker()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "llama3:8b",
        max_tokens: int = 1000,
    ) -> str:
        if not self.circuit_breaker.can_execute(model):
            raise ModelUnreachableError(f"Circuit breaker is OPEN for model {model}")
            
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        
        start_time = time.time()
        try:
            response = requests.post(self.base_url, json=payload, timeout=30.0)
            response.raise_for_status()
            content = response.json().get("response", "")
            
            self.circuit_breaker.record_success(model, latency=time.time() - start_time)
            return content
            
        except requests.exceptions.RequestException as e:
            self.circuit_breaker.record_failure(model)
            raise ModelUnreachableError(f"Ollama unreachable ({self.host}): {e}") from e

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
