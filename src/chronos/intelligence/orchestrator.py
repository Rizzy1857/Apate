"""Bounded lazy generation with Redis leases and fenced content commits."""

import errno
import hashlib
import logging
import os
import stat
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import redis
from chronos.core.content import read_blob
from chronos.intelligence.artifact_policy import ArtifactPolicyEngine
from chronos.intelligence.deterministic_renderer import DeterministicRenderer
from chronos.intelligence.fallback import FallbackProvider
from chronos.intelligence.inference import get_runtime
from chronos.intelligence.prompt_builder import PromptBuilder
from chronos.intelligence.provenance import ProvenanceRecord, GenerationSource
from chronos.intelligence.validator import SemanticValidator

logger = logging.getLogger(__name__)
PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW = 1, 2, 3
LOCK_TTL = 120


class GenerationOrchestrator:
    def __init__(self, redis_client, profile, runtime=None, max_workers=8):
        self.redis = redis_client
        self.profile = profile
        self.runtime = runtime or get_runtime()
        self.policy_engine = ArtifactPolicyEngine()
        self.prompt_builder = PromptBuilder()
        self.validator = SemanticValidator()
        self.fallback_provider = FallbackProvider()
        self.deterministic_renderer = DeterministicRenderer()
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="chronos-gen"
        )
        self._slots = threading.BoundedSemaphore(max_workers)
        self._futures = {}
        self._futures_lock = threading.Lock()

    def _cached(self, meta):
        if meta.get("content_hash"):
            return read_blob(self.redis, meta["content_hash"])
        return None

    def get_or_generate(self, inode, path, session_id, machine_state):
        meta = self.redis.hgetall(f"fs:inode:{inode}")
        if not meta:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")
        if not stat.S_ISREG(int(meta["mode"])):
            raise IsADirectoryError(errno.EISDIR, "Is a directory")
        cached = self._cached(meta)
        if cached is not None:
            return cached
        # Recreating a manifest path does not make an attacker file AI-backed.
        if meta.get("manifest_class", "runtime") not in ("ai_backed", "deterministic"):
            return b""
        future = self._submit(inode, path, session_id)
        if future is None:
            return None
        try:
            return future.result(timeout=10)
        except TimeoutError:
            return None

    def submit_background(
        self, inode, path, session_id, machine_state, priority=PRIORITY_MEDIUM
    ):
        meta = self.redis.hgetall(f"fs:inode:{inode}")
        if (
            meta
            and not meta.get("content_hash")
            and stat.S_ISREG(int(meta["mode"]))
            and meta.get("manifest_class") in ("ai_backed", "deterministic")
        ):
            self._submit(inode, path, session_id)

    def _submit(self, inode, path, session_id):
        with self._futures_lock:
            if inode in self._futures:
                return self._futures[inode]
            if not self._slots.acquire(blocking=False):
                return None
            try:
                future = self._pool.submit(self._resolve, inode, path, session_id)
                self._futures[inode] = future
            except BaseException:
                self._slots.release()
                raise

        # add_done_callback can run immediately: never register while holding this lock.
        def finished(completed):
            with self._futures_lock:
                if self._futures.get(inode) is completed:
                    del self._futures[inode]
            self._slots.release()

        future.add_done_callback(finished)
        return future

    def _resolve(self, inode, path, session_id):
        key, lease = f"fs:inode:{inode}", f"fs:generating:{inode}"
        token = str(uuid.uuid4())
        deadline = time.monotonic() + 10
        # Other owners only wait/read. They never invoke the model without a claim.
        while not self.redis.set(lease, token, nx=True, ex=LOCK_TTL):
            meta = self.redis.hgetall(key)
            if not meta:
                raise FileNotFoundError(errno.ENOENT, "No such file or directory")
            cached = self._cached(meta)
            if cached is not None:
                return cached
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.02)
        try:
            meta = self.redis.hgetall(key)
            if not meta:
                raise FileNotFoundError(errno.ENOENT, "No such file or directory")
            cached = self._cached(meta)
            if cached is not None:
                return cached
            if meta.get("manifest_class") not in ("ai_backed", "deterministic"):
                return b""
            # Only trusted profile facts enter prompts, never attacker history/env.
            machine = self.profile.build_machine_state()
            policy = self.policy_engine.resolve(os.path.basename(path), path, machine)
            source, validated = GenerationSource.TEMPLATE, True
            if meta["manifest_class"] == "deterministic":
                content = self.deterministic_renderer.render(path, machine)
            elif policy.skip_generation:
                content = b""
            elif not self._quota(session_id):
                content = self.fallback_provider.get_degraded_content(
                    os.path.basename(path), policy, path=path, machine_state=machine
                )
                source, validated = GenerationSource.FALLBACK, False
            else:
                content = None
                job_deadline = time.monotonic() + 60.0
                for attempt in range(2):
                    time_left = job_deadline - time.monotonic()
                    if time_left <= 0:
                        break
                    if attempt and not self._quota(session_id):
                        break  # Retries consume the same model-call budget.
                    try:
                        raw = self.runtime.generate(
                            prompt=self.prompt_builder.build(
                                os.path.basename(path), path, machine, policy
                            ),
                            system_prompt=self.prompt_builder.build_system_prompt(
                                machine
                            ),
                            model=policy.model,
                            max_tokens=min(2000, max(1, policy.max_lines or 80) * 10),
                            timeout=time_left
                        )
                        result = self.validator.validate(raw, policy, {**machine, 'artifact_path': path})
                        if result.accepted:
                            content = raw.encode("utf-8")
                            source = GenerationSource.LLM
                            break
                        logger.warning(
                            "Rejected generation inode=%s reason=%s",
                            inode,
                            result.reason,
                        )
                    except Exception:
                        logger.exception("Model failure inode=%s", inode)
                if content is None:
                    content = self.fallback_provider.get_degraded_content(
                        os.path.basename(path), policy, path=path, machine_state=machine
                    )
                    source, validated = GenerationSource.FALLBACK, False
            provenance = ProvenanceRecord(
                model=policy.model,
                generation_source=source,
                file_class=policy.file_class,
                prompt_version="1.0",
                generated_at=str(time.time()),
                validated=validated,
            )
            return self._commit(
                inode, token, meta.get("revision", "0"), content, provenance
            )
        finally:
            self.redis.eval(
                "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0",
                1,
                lease,
                token,
            )

    def _quota(self, session_id):
        window = int(time.time() // 60)
        limit = self.policy_engine.quota_config().get("max_generations_per_minute", 20)
        return bool(
            self.redis.eval(
                """
            local a = tonumber(redis.call('GET', KEYS[1]) or '0')
            local b = tonumber(redis.call('GET', KEYS[2]) or '0')
            if a >= tonumber(ARGV[1]) or b >= 60 then return 0 end
            redis.call('INCR', KEYS[1]); redis.call('EXPIRE', KEYS[1], 120)
            redis.call('INCR', KEYS[2]); redis.call('EXPIRE', KEYS[2], 120)
            return 1
        """,
                2,
                f"chronos:quota:{session_id}:{window}",
                f"chronos:quota:global:{window}",
                limit,
            )
        )

    def _commit(self, inode, token, revision, content, provenance):
        key, lease = f"fs:inode:{inode}", f"fs:generating:{inode}"
        digest = hashlib.sha256(content).hexdigest()
        with self.redis.pipeline() as pipe:
            try:
                pipe.watch(key, lease)
                meta = pipe.hgetall(key)
                if not meta:
                    raise FileNotFoundError(errno.ENOENT, "No such file or directory")
                if (
                    pipe.get(lease) != token
                    or meta.get("revision", "0") != revision
                    or meta.get("content_hash")
                ):
                    return self._cached(meta)
                pipe.multi()
                pipe.set(f"fs:blob:{digest}", content)
                pipe.hset(
                    key,
                    mapping={
                        "content_hash": digest,
                        "size": len(content),
                        "content_state": "generated",
                    },
                )
                pipe.hset(f"fs:blob_meta:{digest}", mapping=provenance.to_dict())
                pipe.execute()
                return content
            except redis.WatchError:
                logger.info("Generation superseded inode=%s", inode)
                return None

    def close(self):
        self._pool.shutdown(wait=True, cancel_futures=True)


def posix_timeout_error():
    return errno.EAGAIN
