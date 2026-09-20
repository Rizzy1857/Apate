"""Recover expired namespaces even when the FUSE process lost its session cache."""
import uuid


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
    return candidates - active


def delete_namespace(client, session_id):
    # Session UUIDs are never reused. No new worker may adopt an expired session.
    if str(uuid.UUID(session_id)) != session_id:
        raise ValueError('Invalid session UUID')
    for key in client.scan_iter(match=f'session:{session_id}:*', count=100):
        client.unlink(key)
    client.delete(f'chronos:machine_state:{session_id}')
