"""Versioned, reproducible resource world. No participant filesystem mutations."""
import hashlib
import random


def snapshot(seed: str, tick: int, interval: int = 60, epoch: int = 0, hostname: str = 'web01') -> dict:
    if tick < 0 or interval < 1:
        raise ValueError('Invalid world clock')
    digest = hashlib.sha256(f'apate-world-v1:{seed}:{tick}'.encode()).digest()
    rng = random.Random(int.from_bytes(digest, 'big'))
    cpu = round(rng.uniform(1, 7), 1)
    total = 16384 * 1024
    used = 2048 * 1024 + rng.randrange(0, 128 * 1024)
    cached = 4096 * 1024 + rng.randrange(0, 128 * 1024)
    from datetime import datetime, timezone
    stamp = datetime.fromtimestamp(epoch + tick * interval, timezone.utc).strftime('%b %d %H:%M:%S')
    return {'schema_version': 1, 'seed': seed, 'tick': tick, 'epoch': epoch,
            'syslog_excerpt': f'{stamp} {hostname} systemd[1]: Completed periodic maintenance.\n',
            'elapsed_seconds': tick * interval, 'uptime': 1209600 + tick * interval,
            'cpu_usage': cpu, 'cpu_system': .5, 'cpu_idle': round(99.5 - cpu, 1),
            'load1': round(cpu / 100, 2), 'load5': .04, 'load15': .05,
            'mem_total': total, 'mem_free': total - used - cached, 'mem_cached': cached}


def publish_tick(client, seed='research-v1', interval=60):
    """CAS publication prevents a delayed writer replacing a newer snapshot."""
    import json
    import time
    client.set('env:world:epoch', int(time.time()), nx=True)
    client.set('env:world:seed', seed, nx=True)
    seed = client.get('env:world:seed')
    if isinstance(seed, bytes):
        seed = seed.decode()
    tick = client.incr('env:world:tick')
    from chronos.intelligence.ubuntu_profile import UbuntuProfile
    state = snapshot(seed, tick, interval, int(client.get('env:world:epoch')) - interval,
                     UbuntuProfile().hostname)
    client.eval('''
        local old = redis.call('GET', KEYS[1])
        if old and tonumber(cjson.decode(old).tick) >= tonumber(ARGV[1]) then return 0 end
        redis.call('SET', KEYS[1], ARGV[2]); return 1
    ''', 1, 'env:world', tick, json.dumps(state))
    return state
