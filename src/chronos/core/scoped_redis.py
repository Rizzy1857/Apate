"""Prefix filesystem keys at the Redis boundary, including Lua and transactions.

Session namespaces isolate attacker writes. Control-plane keys (PID mappings,
global quotas, evidence) intentionally remain outside the filesystem namespace.
"""


class ScopedRedis:
    _first_key = {
        "get",
        "set",
        "setex",
        "hgetall",
        "hget",
        "hset",
        "hsetnx",
        "hincrby",
        "incr",
        "incrby",
        "expire",
        "zscore",
        "zrange",
        "zadd",
        "zrem",
        "zcard",
        "lock",
    }
    _all_keys = {"watch", "delete", "exists"}

    def __init__(self, client, prefix):
        self.client = client
        self.prefix = prefix

    @property
    def connection_pool(self):
        return self.client.connection_pool

    def key(self, value):
        return (
            self.prefix + value
            if isinstance(value, str) and value.startswith("fs:")
            else value
        )

    def script(self, source):
        # Repository Lua builds inode/dentry keys from controlled inode numbers.
        return source.replace("'fs:", "'" + self.prefix + "fs:").replace(
            '"fs:', '"' + self.prefix + "fs:"
        )

    def register_script(self, source):
        script = self.client.register_script(self.script(source))

        def run(keys=None, args=None):
            return script(keys=[self.key(k) for k in (keys or [])], args=args or [])

        return run

    def eval(self, source, count, *args):
        return self.client.eval(
            self.script(source),
            count,
            *[self.key(k) for k in args[:count]],
            *args[count:]
        )

    def pipeline(self):
        return ScopedRedis(self.client.pipeline(), self.prefix)

    def __enter__(self):
        self.client.__enter__()
        return self

    def __exit__(self, *args):
        return self.client.__exit__(*args)

    def __getattr__(self, name):
        if name not in self._first_key | self._all_keys | {'multi', 'execute', 'reset', 'unwatch', 'close'}:
            raise AttributeError(f'Unscoped Redis operation is forbidden: {name}')
        method = getattr(self.client, name)
        if name in self._first_key:
            return lambda key, *args, **kwargs: method(self.key(key), *args, **kwargs)
        if name in self._all_keys:
            return lambda *args, **kwargs: method(
                *[self.key(k) for k in args], **kwargs
            )
        return method
