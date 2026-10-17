"""Explicit cleanup/retention contract for disposable load-test stores."""
import json


def cleanup_pending(client):
    return any(next(client.scan_iter(match=pattern), None) is not None for pattern in (
        'session_pid:*', 'session:*:fs:next_inode', 'session:*:run_id',
        'session:*:context',
    ))


def retained_runs(client, expected):
    records = [client.hgetall(key) for key in client.scan_iter(match='chronos:run:*')]
    assert len(records) == expected, (len(records), expected)
    device_ids = set()
    for record in records:
        run_id = record['run_id']
        assert record['status'] == 'paused', record
        assert client.exists(f'run:{run_id}:fs:next_inode'), 'Retained filesystem missing'
        persona = json.loads(record['persona'])
        assert persona['device_id'] == record['device_id'], 'Run/persona device mismatch'
        device_ids.add(record['device_id'])
    assert len(device_ids) == 1, 'One unchanged profile must resolve to one device'
    assert not cleanup_pending(client), 'Transient session ownership leaked'
    return {'paused_runs': len(records), 'persistent_devices': len(device_ids),
            'transient_ownership_removed': True, 'filesystems_retained': True}
