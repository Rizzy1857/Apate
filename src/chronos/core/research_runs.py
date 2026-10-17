"""Operator-selected persistent runs with one attached session at a time.

SSH participants cannot select a run. The desktop may arm one paused run for
the next authenticated shell. New connections otherwise receive fresh runs.
Only the namespace reaper pauses a run, after draining generation and journals.
"""
import json
import time
import uuid

INDEX = "chronos:runs:index"
NEXT = "chronos:runs:next"


def canonical_id(value):
    parsed = str(uuid.UUID(value))
    if parsed != value:
        raise ValueError("Expected canonical UUID")
    return parsed


def attach_session(client, session_id, persona):
    canonical_id(session_id)
    result = client.eval("""
      local chosen = redis.call('GET', KEYS[1])
      local id = chosen or ARGV[1]
      local run = 'chronos:run:' .. id
      if chosen then
        if redis.call('HGET', run, 'status') ~= 'paused' then
          return redis.error_reply('Run is not paused') end
        if redis.call('HGET', run, 'device_id') ~= ARGV[3] then
          return redis.error_reply('Run profile differs from current device') end
      else
        if redis.call('EXISTS', run) ~= 0 then
          return redis.error_reply('Run ID already exists') end
        redis.call('HSET', run, 'run_id', id, 'device_id', ARGV[3],
          'persona', ARGV[4], 'created_at', ARGV[2], 'cwd', ARGV[5])
        redis.call('ZADD', KEYS[2], ARGV[2], id)
      end
      redis.call('HSET', run, 'status', 'active', 'session_id', ARGV[1],
        'updated_at', ARGV[2])
      redis.call('SET', KEYS[3], id)
      if chosen then redis.call('DEL', KEYS[1]) end
      return redis.call('HGETALL', run)
    """, 3, NEXT, INDEX, f"session:{session_id}:run_id", session_id,
        str(time.time()), persona["device_id"], json.dumps(persona, sort_keys=True),
        f"/home/{persona['primary_user']}")
    return dict(zip(result[::2], result[1::2]))


def namespace_prefix(client, session_id):
    canonical_id(session_id)
    run_id = client.get(f"session:{session_id}:run_id")
    if not run_id:
        return f"session:{session_id}:"
    canonical_id(run_id)
    owner = client.hget(f"chronos:run:{run_id}", "session_id")
    status = client.hget(f"chronos:run:{run_id}", "status")
    if owner != session_id or status != "active":
        raise PermissionError("Run session ownership mismatch")
    return f"run:{run_id}:"


def pause_session(client, session_id):
    canonical_id(session_id)
    return client.eval("""
      local id = redis.call('GET', KEYS[1])
      if not id then return 0 end
      local run = 'chronos:run:' .. id
      if redis.call('HGET', run, 'session_id') ~= ARGV[1] then return 0 end
      redis.call('HSET', run, 'status', 'paused', 'updated_at', ARGV[2])
      return 1
    """, 1, f"session:{session_id}:run_id", session_id, str(time.time()))


def arm_resume(client, run_id):
    canonical_id(run_id)
    return client.eval("""
      if redis.call('HGET', KEYS[1], 'status') ~= 'paused' then
        return redis.error_reply('Only paused runs can resume') end
      redis.call('SET', KEYS[2], ARGV[1], 'EX', 60)
      return 1
    """, 2, f"chronos:run:{run_id}", NEXT, run_id)


def update_run_context(client, session_id, cwd):
    canonical_id(session_id)
    return client.eval("""
      local id = redis.call('GET', KEYS[1])
      if not id then return 0 end
      local run = 'chronos:run:' .. id
      if redis.call('HGET', run, 'session_id') ~= ARGV[1]
        or redis.call('HGET', run, 'status') ~= 'active' then
        return redis.error_reply('Run ownership lost') end
      redis.call('HSET', run, 'cwd', ARGV[2], 'updated_at', ARGV[3])
      return 1
    """, 1, f"session:{session_id}:run_id", session_id, cwd, str(time.time()))
