"""Operational snapshots, never authoritative persona or executable input."""
import time
import uuid


def publish_context(client, session_id, environment, command_id=""):
    session_id = str(uuid.UUID(session_id))
    if command_id:
        command_id = str(uuid.UUID(command_id))
    snapshot = {
        "schema_version": "1",
        "session_id": session_id,
        "effective_username": environment.username,
        "cwd": environment.cwd,
        "home": environment.env["HOME"],
        "last_command_id": command_id,
        "updated_at": str(time.time()),
        "device_id": getattr(environment, "machine_state", {}).get("device_id", ""),
    }
    # Same namespace as session filesystem state: cleanup cannot leave a live
    # status record behind. Audit history, not this projection, is evidence.
    client.hset(f"session:{session_id}:context", mapping=snapshot)
    from chronos.core.research_runs import update_run_context
    update_run_context(client, session_id, environment.cwd)
    return snapshot
