"""Expiring operational heartbeat, separate from participant evidence."""
import logging
import threading
import time


def publish_health(client, persistence, streamer):
    now = time.time()
    worker = persistence.worker_thread
    watcher = streamer.thread if streamer is not None else None
    polled = streamer.last_success_at if streamer is not None else 0
    error = streamer.health_error if streamer is not None else "unavailable"
    audit_error = persistence.audit_health_error
    activity = persistence.audit_last_activity
    if watcher is None or not watcher.is_alive():
        error = error or "watcher_stopped"
    elif not polled or now - polled >= 10:
        error = error or "poll_stalled"
    if worker is None or not worker.is_alive():
        audit_error = audit_error or "worker_stopped"
    elif not activity or now - activity >= 10:
        audit_error = audit_error or "worker_stalled"
    healthy = bool(worker and worker.is_alive() and watcher and watcher.is_alive()
                   and polled and now - polled < 10 and not error
                   and activity and now - activity < 10 and audit_error in ("", "starting"))
    state = {"updated_at": str(now), "status": "healthy" if healthy else "degraded",
             "outbox_pending": str(persistence.spool.count()),
             "audit_worker_alive": "1" if worker and worker.is_alive() else "0",
             "audit_last_activity": str(activity), "audit_error": audit_error,
             "watcher_alive": "1" if watcher and watcher.is_alive() else "0",
             "watcher_last_success": str(polled), "watcher_error": error,
             "watcher_last_event_id": str(streamer.last_id if streamer is not None else 0)}
    with client.pipeline() as pipe:
        pipe.multi()
        pipe.hset("chronos:operational_health", mapping=state)
        pipe.expire("chronos:operational_health", 8)
        pipe.execute()
    return state


def start_health_publisher(client, persistence, streamer):
    def publish():
        while True:
            try:
                publish_health(client, persistence, streamer)
            except Exception:
                logging.warning("Operational heartbeat unavailable")
            time.sleep(2)
    threading.Thread(target=publish, name="operational-health", daemon=True).start()
