import stat
import threading
import time
import uuid
from types import SimpleNamespace

from chronos.core.audit_spool import AuditSpool
from chronos.core.operational_health import publish_health
from chronos.intelligence.orchestrator import GenerationOrchestrator
from chronos.intelligence.ubuntu_profile import UbuntuProfile


def test_health_detects_stalled_watcher_and_delivery_failure(isolated_redis, tmp_path):
    spool = AuditSpool(str(tmp_path / "audit.sqlite3"))
    try:
        live = SimpleNamespace(is_alive=lambda: True)
        persistence = SimpleNamespace(worker_thread=live, spool=spool,
                                      audit_last_activity=time.time(), audit_health_error="")
        streamer = SimpleNamespace(thread=live, last_success_at=time.time(),
                                   health_error="", last_id=12)
        assert publish_health(isolated_redis, persistence, streamer)["status"] == "healthy"
        spool.append(["synthetic pending event"])
        persistence.audit_health_error = "delivery_failed"
        snapshot = publish_health(isolated_redis, persistence, streamer)
        assert snapshot["status"] == "degraded" and snapshot["outbox_pending"] == "1"
        persistence.audit_health_error = ""
        streamer.last_success_at = time.time() - 60
        stalled = publish_health(isolated_redis, persistence, streamer)
        assert stalled["status"] == "degraded"
        assert stalled["watcher_error"] == "poll_stalled"
        assert 0 < isolated_redis.ttl("chronos:operational_health") <= 8
    finally:
        spool.close()


def test_generation_status_tracks_inflight_then_finished_artifact(isolated_redis):
    r = isolated_redis
    r.hset("fs:inode:9", mapping={"mode": str(stat.S_IFREG | 0o644),
                                 "manifest_class": "deterministic", "revision": "0"})
    profile = UbuntuProfile()
    session_id = str(uuid.uuid4())
    machine = profile.get_or_create_machine_state(r, session_id)
    generator = GenerationOrchestrator(r, profile, inference_mode="deterministic")
    entered, release = threading.Event(), threading.Event()
    render = generator.deterministic_renderer.render

    def blocked_render(path, state):
        entered.set()
        assert release.wait(5)
        return render(path, state)

    generator.deterministic_renderer.render = blocked_render
    try:
        generator.submit_background(9, "/etc/hostname", session_id, machine)
        assert entered.wait(3)
        keys = list(r.scan_iter(f"session:{session_id}:generation:*"))
        assert len(keys) == 1
        assert r.hget(keys[0], "phase") == "resolving"
        release.set()
        generator.close()
        assert r.hget(keys[0], "phase") == "finished"
        digest = r.hget("fs:inode:9", "content_hash")
        assert r.hget(f"fs:blob_meta:{digest}", "prompt_version") == "2.0-persona"
        assert r.get(f"fs:blob:{digest}").strip() == profile.hostname
        assert 0 < r.ttl(keys[0]) <= 120
    finally:
        release.set()
        generator.close()
