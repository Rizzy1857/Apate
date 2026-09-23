from chronos.simulation.world_state import snapshot, publish_tick
from chronos.gateway.dispatcher import SessionEnvironment, CommandRegistry


def test_seeded_world_coherence():
    first, second = snapshot('test', 1), snapshot('test', 2)
    assert first == snapshot('test', 1)
    assert second['uptime'] - first['uptime'] == 60
    assert first['cpu_usage'] + first['cpu_system'] + first['cpu_idle'] == 100
    env = SessionEnvironment()
    env.world_state = first
    registry = CommandRegistry(env)
    free = registry._handle_free([], b'')[1].decode()
    top = registry._handle_top([], b'')[1].decode()
    assert f"{first['cpu_usage']} us" in top
    assert f"{first['mem_free'] // 1024}Mi" in free
    assert first['mem_free'] + first['mem_cached'] < first['mem_total']


def test_world_clock_survives_publisher_restart(isolated_redis):
    import json
    first = publish_tick(isolated_redis)
    second = publish_tick(isolated_redis)
    assert second['tick'] == first['tick'] + 1
    assert json.loads(isolated_redis.get('env:world')) == second
    assert not list(isolated_redis.scan_iter(match='session:*'))


def test_world_log_never_overwrites_participant_content(isolated_redis):
    import hashlib
    from chronos.simulation.world_files import refresh_syslog
    from chronos.core.content import mutate_content, read_blob
    from chronos.core.scoped_redis import ScopedRedis
    client = ScopedRedis(isolated_redis, 'session:world-test:')
    original = b'baseline\n'
    digest = hashlib.sha256(original).hexdigest()
    client.set(f'fs:blob:{digest}', original)
    client.hset('fs:inode:2', mapping={'mode': 0o100644, 'content_hash': digest,
                                     'content_state': 'prepared', 'revision': 0})
    publish_tick(isolated_redis)
    assert refresh_syslog(client, 2)
    meta = client.hgetall('fs:inode:2')
    content = read_blob(client, meta['content_hash'])
    assert content.startswith(original)
    assert len(content) == int(meta['size'])
    assert not refresh_syslog(client, 2)
    mutate_content(client, 2, length=0)
    mutate_content(client, 2, buf=b'participant')
    publish_tick(isolated_redis)
    assert not refresh_syslog(client, 2)
    assert read_blob(client, client.hget('fs:inode:2', 'content_hash')) == b'participant'
