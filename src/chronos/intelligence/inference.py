"""
inference.py
------------
Local inference runtime targeting the Ollama container on chronos-net.
"""

import os
import requests
import time
import random
import threading
import json
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

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
                    if health.state == BreakerState.OPEN and current_time >= health.next_retry:
                        health.state = BreakerState.HALF_OPEN
                        return True
                return False
            return False
        if health.state == BreakerState.HALF_OPEN:
            return False
        return False

    def record_success(self, model: str, latency: float = 0.0):
        health = self._get_health(model)
        health.successes += 1
        health.failures = 0
        health.state = BreakerState.CLOSED
        health.last_success = time.time()
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
            exponent = max(0, health.failures - self.failure_threshold)
            backoff = min(self.max_backoff, self.base_backoff * (2 ** exponent))
            jitter = random.uniform(0.8, 1.2)
            health.next_retry = time.time() + (backoff * jitter)

class InferenceRuntime:
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
        timeout: float = 30.0,
    ) -> str:
        if not self.circuit_breaker.can_execute(model):
            logger.error(f"Circuit breaker is OPEN for model {model}")
            raise ModelUnreachableError(f"Circuit breaker is OPEN for model {model}")
            
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1
            },
        }
        
        start_time = time.time()
        deadline = time.monotonic() + timeout
        logger.info(f"Starting generation for model {model}, max_tokens {max_tokens}, timeout {timeout:.1f}s")
        try:
            request_start = time.monotonic()
            response = requests.post(self.base_url, json=payload, timeout=(3.0, timeout), stream=True,
                                     allow_redirects=False)
            
            # Enforce absolute deadline against blocking reads
            timer = threading.Timer(max(0.1, deadline - time.monotonic()), response.close)
            timer.start()
            
            first_byte_time = time.monotonic()
            logger.info(f"[{model}] Time to first streamed response: {first_byte_time - request_start:.3f}s")
            
            try:
                response.raise_for_status()
                pending = bytearray()
                parts = []
                received = 0
                completed = False
                event_count = 0
                eval_count = None
                eval_duration = None
                try:
                    for chunk in response.iter_content(chunk_size=128):
                        pending.extend(chunk)
                        received += len(chunk)
                        if received > 262144 or time.monotonic() > deadline:
                            logger.error(f"[{model}] Deadline exceeded or limit hit. received={received}, time={time.monotonic() - request_start:.3f}s")
                            raise requests.exceptions.RequestException('Model response limit exceeded')
                        while b'\n' in pending:
                            line, _, remainder = pending.partition(b'\n')
                            pending = bytearray(remainder)
                            if not line.strip():
                                continue
                            event = json.loads(line)
                            event_count += 1
                            if (not isinstance(event, dict) or not isinstance(event.get('response'), str)
                                    or not isinstance(event.get('done'), bool) or completed):
                                raise ValueError('Invalid model stream schema')
                            parts.append(event['response'])
                            completed = event['done']
                            if completed:
                                logger.info(f"[{model}] Completed. tokens={event.get('eval_count', 0)}, eval_duration={event.get('eval_duration', 0)/1e9:.3f}s, prompt_eval_duration={event.get('prompt_eval_duration', 0)/1e9:.3f}s")
                            if event.get('done_reason') == 'length':
                                logger.error(f"[{model}] Model output truncated at token limit")
                                raise ValueError('Model output truncated at token limit')
                except (Exception, AttributeError) as e:
                    if time.monotonic() >= deadline:
                        logger.error(f"[{model}] Absolute deadline exceeded during read. time={time.monotonic() - request_start:.3f}s")
                        raise requests.exceptions.RequestException('Model response limit exceeded')
                    raise e
                    
                if pending.strip() or not completed:
                    logger.error(f"[{model}] Incomplete model stream")
                    raise ValueError('Incomplete model stream')
                content = ''.join(parts)
            finally:
                timer.cancel()
                response.close()
            
            self.circuit_breaker.record_success(model, latency=time.time() - start_time)
            return content
            
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"[{model}] Generation failed: {e}")
            self.circuit_breaker.record_failure(model)
            raise ModelUnreachableError(f"Ollama unreachable ({self.host}): {e}") from e

    def health_check(self) -> bool:
        try:
            response = requests.get(
                f"http://{self.host}:11434/api/tags", timeout=5.0
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

def get_runtime() -> InferenceRuntime:
    return InferenceRuntime()
