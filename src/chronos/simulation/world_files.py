"""Apply bounded synthetic log updates without overwriting participant versions."""
import hashlib
import json
import redis
from chronos.core.content import read_blob


def refresh_syslog(client, inode):
    raw = client.get('env:world')
    if not raw:
        return False
    world = json.loads(raw)
    key = f'fs:inode:{inode}'
    with client.pipeline() as pipe:
        try:
            pipe.watch(key)
            meta = pipe.hgetall(key)
            if (not meta or not meta.get('content_hash') or meta.get('content_state') == 'written'
                    or int(meta.get('world_tick', -1)) >= world['tick']):
                return False
            base_hash = meta.get('world_base_hash', meta['content_hash'])
            base = read_blob(client, base_hash)
            content = base.rstrip(b'\n') + b'\n' + world['syslog_excerpt'].encode()
            if len(content) > 65536:
                return False
            digest = hashlib.sha256(content).hexdigest()
            pipe.multi()
            pipe.set(f'fs:blob:{digest}', content)
            pipe.hset(f'fs:blob_meta:{digest}', mapping={
                'generation_source': 'world', 'validated': 'true',
                'world_tick': world['tick'], 'seed': world['seed'], 'base_hash': base_hash,
            })
            pipe.hset(key, mapping={'content_hash': digest, 'size': len(content),
                                   'content_state': 'world_generated', 'world_base_hash': base_hash,
                                   'world_tick': world['tick'], 'mtime': world['epoch'] + world['elapsed_seconds']})
            pipe.hincrby(key, 'revision', 1)
            pipe.execute()
            return True
        except redis.WatchError:
            return False
