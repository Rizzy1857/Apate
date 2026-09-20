"""Atomic binary content updates with bounded file size."""

import errno
import hashlib
import time
import stat
import redis

MAX_FILE_BYTES = 1024 * 1024
MAX_SESSION_BLOB_BYTES = 16 * 1024 * 1024


def read_blob(client, digest):
    options = dict(client.connection_pool.connection_kwargs)
    options["decode_responses"] = False
    key = f"fs:blob:{digest}"
    from chronos.core.scoped_redis import ScopedRedis

    if isinstance(client, ScopedRedis):
        key = client.key(key)
    pool = redis.ConnectionPool(
        connection_class=client.connection_pool.connection_class, **options
    )
    try:
        value = redis.Redis(connection_pool=pool).get(key)
    finally:
        pool.disconnect()
    if value is None:
        raise OSError(errno.EIO, "Input/output error")
    return value


def mutate_content(client, inode, *, buf=None, offset=0, length=None):
    if offset < 0 or (length is not None and length < 0):
        raise OSError(errno.EINVAL, "Invalid argument")
    end = length if length is not None else offset + len(buf)
    if end > MAX_FILE_BYTES:
        raise OSError(errno.EFBIG, "File too large")
    key = f"fs:inode:{inode}"
    with client.pipeline() as pipe:
        for _ in range(32):
            try:
                pipe.watch(key, "fs:bytes_allocated")
                meta = pipe.hgetall(key)
                if not meta:
                    raise OSError(errno.ENOENT, "No such file or directory")
                if not stat.S_ISREG(int(meta['mode'])):
                    raise OSError(errno.EISDIR, 'Is a directory')
                old = (
                    read_blob(client, meta["content_hash"])
                    if meta.get("content_hash")
                    else b""
                )
                if length is not None:
                    content = old[:length].ljust(length, b"\0")
                else:
                    old = old.ljust(offset, b"\0")
                    content = old[:offset] + buf + old[offset + len(buf) :]
                digest = hashlib.sha256(content).hexdigest()
                allocated = int(pipe.get("fs:bytes_allocated") or 0)
                if allocated + len(content) > MAX_SESSION_BLOB_BYTES:
                    raise OSError(errno.ENOSPC, "No space left on device")
                pipe.multi()
                # Conservative allocation budget includes superseded versions until cleanup.
                pipe.incrby("fs:bytes_allocated", len(content))
                pipe.set(f"fs:blob:{digest}", content)
                pipe.hset(
                    key,
                    mapping={
                        "content_hash": digest,
                        "size": len(content),
                        "mtime": time.time(),
                        "content_state": "written",
                    },
                )
                pipe.hincrby(key, "revision", 1)
                pipe.delete(f"fs:generating:{inode}")
                pipe.execute()
                return
            except redis.WatchError:
                continue
    raise OSError(errno.EAGAIN, "Resource temporarily unavailable")
