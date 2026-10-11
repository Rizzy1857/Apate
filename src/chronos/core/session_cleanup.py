"""Recover expired namespaces even when the FUSE process lost its session cache."""
import time
import uuid


LIFECYCLE_KEY = "session:{session_id}:lifecycle_recovery"


def register_lifecycle(client, session_id, *, origin, identity):
    """Persist enough data to close an admitted session after server death."""
    recovery_id = str(uuid.uuid4())
    mapping = {
        "operation_id": recovery_id,
        "origin": origin,
        "claimed_username": identity.get("claimed_username") or "",
        "effective_username": identity.get("effective_username") or "",
        "identity_mismatch": "1" if identity.get("identity_mismatch") else "0",
        "identity_policy": identity.get("identity_policy") or "",
    }
    client.hset(LIFECYCLE_KEY.format(session_id=session_id), mapping=mapping)
    return mapping


def prepare_disconnect(client, session_id, *, outcome, reason):
    """Freeze one byte-stable close record; the first closer determines its cause."""
    key = LIFECYCLE_KEY.format(session_id=session_id)
    script = """
    if redis.call('EXISTS', KEYS[1]) == 0 then return {} end
    if redis.call('HEXISTS', KEYS[1], 'completed_at') == 0 then
      redis.call('HSET', KEYS[1], 'completed_at', ARGV[1],
        'outcome', ARGV[2], 'reason', ARGV[3])
    end
    return redis.call('HGETALL', KEYS[1])
    """
    raw = client.eval(script, 1, key, repr(time.time()), outcome, reason)
    if not raw:
        return None
    record = dict(zip(raw[::2], raw[1::2]))
    return {
        "operation_id": record["operation_id"],
        "completed_at": float(record["completed_at"]),
        "outcome": record["outcome"],
        "reason": record["reason"],
        "origin": record.get("origin") or "unattributed",
        "claimed_username": record.get("claimed_username") or None,
        "effective_username": record.get("effective_username") or None,
        "identity_mismatch": record.get("identity_mismatch") == "1",
        "identity_policy": record.get("identity_policy") or None,
        "idempotency_scope": "lifecycle-recovery-v1",
        "schema_version": 1,
    }


def acknowledge_disconnect(client, session_id):
    client.delete(LIFECYCLE_KEY.format(session_id=session_id))


def orphan_sessions(client):
    active = set()
    for key in client.scan_iter(match='session_pid:*', count=100):
        value = client.get(key)
        if value:
            active.add(value.decode() if isinstance(value, bytes) else value)
    candidates = set()
    for key in client.scan_iter(match='session:*:fs:next_inode', count=100):
        key = key.decode() if isinstance(key, bytes) else key
        sid = key.split(':')[1]
        try:
            if str(uuid.UUID(sid)) == sid:
                candidates.add(sid)
        except ValueError:
            continue
    for key in client.scan_iter(match='session:*:lifecycle_recovery', count=100):
        key = key.decode() if isinstance(key, bytes) else key
        sid = key.split(':')[1]
        try:
            if str(uuid.UUID(sid)) == sid:
                candidates.add(sid)
        except ValueError:
            continue
    return candidates - active


def delete_namespace(client, session_id):
    # Session UUIDs are never reused. No new worker may adopt an expired session.
    if str(uuid.UUID(session_id)) != session_id:
        raise ValueError('Invalid session UUID')
    for key in client.scan_iter(match=f'session:{session_id}:*', count=100):
        client.unlink(key)
    client.delete(f'chronos:machine_state:{session_id}')
