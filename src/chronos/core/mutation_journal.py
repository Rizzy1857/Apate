"""Redis state-associated mutation journal used for crash reconciliation."""

import time


JOURNAL_INDEX = "fs:mutation_journal"


def journal_mapping(operation_id, operation, path, command_id, origin, inode=0):
    return {
        "operation_id": operation_id,
        "operation": operation,
        "path": path,
        "inode": inode,
        "command_id": command_id or "",
        "origin": origin or "unattributed",
        "completed_at": time.time(),
        "schema_version": 1,
    }


def add_to_pipeline(pipe, mapping):
    operation_id = mapping["operation_id"]
    pipe.hset(f"fs:mutation:{operation_id}", mapping=mapping)
    pipe.zadd(JOURNAL_INDEX, {operation_id: float(mapping["completed_at"])})


def acknowledge(client, operation_id):
    with client.pipeline() as pipe:
        pipe.multi()
        pipe.delete(f"fs:mutation:{operation_id}")
        pipe.zrem(JOURNAL_INDEX, operation_id)
        pipe.execute()


def pending(client):
    records = []
    for operation_id in client.zrange(JOURNAL_INDEX, 0, -1):
        operation_id = (
            operation_id.decode() if isinstance(operation_id, bytes) else operation_id
        )
        record = client.hgetall(f"fs:mutation:{operation_id}")
        if record:
            records.append(record)
        else:
            client.zrem(JOURNAL_INDEX, operation_id)
    return records
