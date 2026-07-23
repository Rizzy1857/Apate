"""
orchestrator.py
---------------
Non-blocking generation orchestration for ChronosFUSE.

The FUSE read() hot path must never block indefinitely on an LLM call.
This module handles:
  - Background generation pool (ThreadPoolExecutor)
  - Redis-backed dedup locks (fs:generating:<inode>, TTL 30s)
  - Adaptive timeouts (P95 latency per model + 2.0s safety margin)
  - Per-session inference quotas (token bucket via Redis)
  - POSIX-realistic error responses on timeout (EAGAIN / ETIMEDOUT / EIO)
  - Background completion: generation persists even after timeout

Guardrails (hard rules, never violated):
  1. AI never owns state truth — blob content only, never inode/directory state.
  2. No AI call blocks a syscall indefinitely — every path has a hard timeout.
  3. Timeout returns a realistic POSIX error, not an "AI unavailable" message.
  4. Generation continues in background after timeout and is cached on completion.
"""

import errno
import hashlib
import json
import random
import time
import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Callable, Dict, Optional

from chronos.intelligence.artifact_policy import ArtifactPolicy, ArtifactPolicyEngine
from chronos.intelligence.prompt_builder import PromptBuilder
from chronos.intelligence.inference import InferenceRuntime, get_runtime
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.validator import SemanticValidator
from chronos.intelligence.fallback import FallbackProvider
from chronos.intelligence.inference import ModelUnreachableError
from chronos.intelligence.provenance import ProvenanceRecord, GenerationSource

# Generation priority levels (used for future prioritization)
PRIORITY_HIGH = 1    # on create()
PRIORITY_MEDIUM = 2  # on readdir() prewarm
PRIORITY_LOW = 3     # background idle

# Prometheus metrics — optional, fail silently if prometheus_client not present
try:
    from prometheus_client import Histogram, Counter
    _generation_latency = Histogram(
        "chronos_generation_latency_seconds",
        "Time from generation start to completion",
        ["model", "file_class"],
    )
    _timeout_counter = Counter(
        "chronos_generation_timeouts_total",
        "Count of generation timeouts returned to FUSE",
        ["model"],
    )
    _quota_counter = Counter(
        "chronos_inference_quota_exhausted_total",
        "Count of generations skipped due to session quota",
        ["session_id"],
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

# Latency history stored in Redis: chronos:metrics:latency:<model> → JSON list of seconds
_LATENCY_KEY = "chronos:metrics:latency:{model}"
_LATENCY_WINDOW = 50      # rolling window size for P95 calculation
_SAFETY_MARGIN = 2.0      # seconds added on top of P95
_DEFAULT_TIMEOUT = 10.0   # used when no latency history is available
_LOCK_TTL = 30            # seconds for the Redis generation dedup lock
_PREWARM_LIMIT = 5        # max concurrent background prewarms per readdir()
_QUOTA_WINDOW = 60        # seconds for the per-session quota window


class GenerationOrchestrator:
    """
    Manages background file content generation for ChronosFUSE.

    One instance is shared by the entire FUSE process.
    Thread-safe: all shared state is protected by Redis or threading primitives.
    """

    def __init__(
        self,
        redis_client,
        profile: UbuntuProfile,
        runtime: Optional[InferenceRuntime] = None,
        max_workers: int = 8,
    ):
        self.redis = redis_client
        self.profile = profile
        self.runtime = runtime or get_runtime()
        self.policy_engine = ArtifactPolicyEngine()
        self.prompt_builder = PromptBuilder()
        self.validator = SemanticValidator()
        self.fallback_provider = FallbackProvider()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="chronos-gen")

        # In-flight futures: inode → Future
        self._futures: Dict[int, Future] = {}
        self._futures_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API — called from ChronosFUSE
    # ------------------------------------------------------------------

    def get_or_generate(
        self,
        inode: int,
        path: str,
        session_id: str,
        machine_state: Dict[str, Any],
    ) -> Optional[bytes]:
        """
        Called from FUSE read() on a cache-miss.

        Returns content bytes if generation completes within the adaptive timeout.
        Returns None if the timeout is exceeded (caller should raise FuseOSError).
        Generation continues in the background regardless of the return value.
        """
        import os
        filename = os.path.basename(path)

        # Resolve artifact policy before anything else
        policy = self.policy_engine.resolve(filename, path)

        # Fast path: empty category — no AI needed
        if policy.skip_generation:
            self._persist_empty(inode)
            return b""

        # Check per-session inference quota
        if not self._check_and_decrement_quota(session_id, policy):
            return self.fallback_provider.get_degraded_content(filename, policy)

        # Submit or attach to existing generation future
        future = self._get_or_submit(inode, path, filename, session_id, machine_state, policy, PRIORITY_HIGH)

        # Adaptive wait
        timeout = self._adaptive_timeout(policy.model)
        try:
            result = future.result(timeout=timeout)
            return result
        except FutureTimeoutError:
            if _PROMETHEUS_AVAILABLE:
                _timeout_counter.labels(model=policy.model).inc()
            return None   # caller raises a randomized POSIX error

    def submit_background(
        self,
        inode: int,
        path: str,
        session_id: str,
        machine_state: Dict[str, Any],
        priority: int = PRIORITY_MEDIUM,
    ) -> None:
        """
        Called from FUSE create() and readdir() for fire-and-forget prewarm.
        Does not block. Does not return a result.
        """
        import os
        filename = os.path.basename(path)
        policy = self.policy_engine.resolve(filename, path)

        if policy.skip_generation:
            self._persist_empty(inode)
            return

        self._get_or_submit(inode, path, filename, session_id, machine_state, policy, priority)

    # ------------------------------------------------------------------
    # Internal generation machinery
    # ------------------------------------------------------------------

    def _get_or_submit(
        self,
        inode: int,
        path: str,
        filename: str,
        session_id: str,
        machine_state: Dict[str, Any],
        policy: ArtifactPolicy,
        priority: int,
    ) -> Future:
        with self._futures_lock:
            if inode in self._futures and not self._futures[inode].done():
                return self._futures[inode]

            # Acquire Redis dedup lock so other FUSE worker threads don't duplicate
            lock_key = f"fs:generating:{inode}"
            if not self.redis.set(lock_key, session_id, nx=True, ex=_LOCK_TTL):
                # Another thread holds the lock — attach to its future if we have one
                if inode in self._futures:
                    return self._futures[inode]

            future = self._pool.submit(
                self._generate_and_persist,
                inode, path, filename, session_id, machine_state, policy,
            )
            self._futures[inode] = future
            return future

    def _generate_and_persist(
        self,
        inode: int,
        path: str,
        filename: str,
        session_id: str,
        machine_state: Dict[str, Any],
        policy: ArtifactPolicy,
    ) -> bytes:
        """
        Runs in a background thread.
        Generates content, validates it, and persists it to Redis.
        Returns the final bytes regardless of who (if anyone) is still waiting.
        """
        start = time.monotonic()
        lock_key = f"fs:generating:{inode}"

        try:
            system_prompt = self.prompt_builder.build_system_prompt(machine_state)
            prompt = self.prompt_builder.build(filename, path, machine_state, policy)

            retry_count = 0
            content_bytes = b""
            
            provenance = ProvenanceRecord(
                model=policy.model,
                generation_source=GenerationSource.LLM,
                file_class=policy.file_class,
                prompt_version="1.0",
                generated_at=str(time.time()),
                validated=True
            )
            
            try:
                while retry_count < 2:
                    raw = self.runtime.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        model=policy.model,
                        max_tokens=policy.max_lines * 10 if policy.max_lines else 1000,
                    )
                    result = self.validator.validate(raw, policy, machine_state)
                    if result.accepted:
                        content_bytes = raw.encode("utf-8")
                        break
                    retry_count += 1
            except ModelUnreachableError:
                # Infrastructure failure: immediately fall back without validating
                content_bytes = self.fallback_provider.get_degraded_content(filename, policy)
                provenance.generation_source = GenerationSource.FALLBACK
                provenance.validated = False

            if not content_bytes:
                # Validator rejected twice — use static template
                content_bytes = self.fallback_provider.get_degraded_content(filename, policy)
                provenance.generation_source = GenerationSource.TEMPLATE
                provenance.validated = False

            # Persist blob + inode metadata + provenance
            self._persist(inode, content_bytes, policy, provenance)

            elapsed = time.monotonic() - start
            self._record_latency(policy.model, elapsed)
            if _PROMETHEUS_AVAILABLE:
                _generation_latency.labels(model=policy.model, file_class=policy.file_class).observe(elapsed)

            return content_bytes

        except Exception as e:
            print(f"[Orchestrator] Generation error for inode {inode} path={path}: {e}")
            fallback = self.fallback_provider.get_degraded_content(filename, policy)
            provenance = ProvenanceRecord(
                model=policy.model,
                generation_source=GenerationSource.FALLBACK,
                file_class=policy.file_class,
                prompt_version="1.0",
                generated_at=str(time.time()),
                validated=False
            )
            self._persist(inode, fallback, policy, provenance)
            return fallback
        finally:
            self.redis.delete(lock_key)
            with self._futures_lock:
                self._futures.pop(inode, None)

    def _persist(
        self,
        inode: int,
        content: bytes,
        policy: ArtifactPolicy,
        provenance: ProvenanceRecord,
    ) -> None:
        """Persist content blob, inode content_hash, and provenance metadata."""
        blob_hash = hashlib.sha256(content).hexdigest()

        # Content blob
        self.redis.set(f"fs:blob:{blob_hash}", content)

        # Inode metadata
        self.redis.hset(f"fs:inode:{inode}", mapping={
            "content_hash": blob_hash,
            "size": len(content),
            "mtime": time.time(),
            "artifact_category": policy.category,
            "artifact_class": policy.file_class,
        })

        # Provenance (M2.H)
        self.redis.hset(f"fs:blob_meta:{blob_hash}", mapping=provenance.to_dict())

    def _persist_empty(self, inode: int) -> None:
        """Persist an empty blob for files whose artifact policy is 'empty'."""
        blob_hash = hashlib.sha256(b"").hexdigest()
        self.redis.set(f"fs:blob:{blob_hash}", b"")
        self.redis.hset(f"fs:inode:{inode}", mapping={
            "content_hash": blob_hash,
            "size": 0,
            "mtime": time.time(),
            "artifact_category": "empty",
        })

    # ------------------------------------------------------------------
    # Adaptive timeout
    # ------------------------------------------------------------------

    def _adaptive_timeout(self, model: str) -> float:
        """
        Compute timeout = P95(recent latency for model) + SAFETY_MARGIN.
        Falls back to DEFAULT_TIMEOUT when insufficient history.
        """
        key = _LATENCY_KEY.format(model=model)
        raw = self.redis.get(key)
        if not raw:
            return _DEFAULT_TIMEOUT
        try:
            samples = json.loads(raw)
            if len(samples) < 5:
                return _DEFAULT_TIMEOUT
            samples_sorted = sorted(samples)
            p95_index = int(len(samples_sorted) * 0.95)
            return samples_sorted[p95_index] + _SAFETY_MARGIN
        except (json.JSONDecodeError, IndexError):
            return _DEFAULT_TIMEOUT

    def _record_latency(self, model: str, elapsed: float) -> None:
        """Push a latency sample into the rolling window for the given model."""
        key = _LATENCY_KEY.format(model=model)
        raw = self.redis.get(key)
        samples = json.loads(raw) if raw else []
        samples.append(elapsed)
        if len(samples) > _LATENCY_WINDOW:
            samples = samples[-_LATENCY_WINDOW:]
        self.redis.set(key, json.dumps(samples))

    # ------------------------------------------------------------------
    # Inference quota (per session, token bucket via Redis)
    # ------------------------------------------------------------------

    def _check_and_decrement_quota(self, session_id: str, policy: ArtifactPolicy) -> bool:
        """
        Returns True if the session is within quota, False if exhausted.
        Uses a simple sliding window counter in Redis.
        """
        quota_cfg = self.policy_engine.quota_config()
        max_per_minute = quota_cfg.get("max_generations_per_minute", 20)

        bucket_key = f"chronos:quota:{session_id}:{int(time.time() // _QUOTA_WINDOW)}"
        count = self.redis.incr(bucket_key)
        if count == 1:
            self.redis.expire(bucket_key, _QUOTA_WINDOW * 2)

        if count > max_per_minute:
            if _PROMETHEUS_AVAILABLE:
                _quota_counter.labels(session_id=session_id).inc()
            return False
        return True


def posix_timeout_error() -> int:
    """Return a randomized realistic POSIX errno for a timeout response."""
    return random.choice([errno.EAGAIN, errno.ETIMEDOUT, errno.EIO])
