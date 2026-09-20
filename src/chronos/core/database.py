import os
import redis
import time
import errno
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, prefix=None):
        self.redis_host = os.environ.get("REDIS_HOST", "localhost")
        self.redis_port = int(os.environ.get("REDIS_PORT", 6379))
        self.client = redis.Redis(
            host=self.redis_host, 
            port=self.redis_port, 
            socket_timeout=3,
            socket_connect_timeout=3,
            decode_responses=True
        )
        if prefix:
            from chronos.core.scoped_redis import ScopedRedis
            self.client = ScopedRedis(self.client, prefix)
        self._load_scripts()

    def _load_scripts(self):
        """Load Lua scripts for atomic operations"""
        self.scripts = {}
        script_dir = os.path.join(os.path.dirname(__file__), "lua")
        
        # Ensure directory exists (might not if we run this before creating it)
        if not os.path.exists(script_dir):
            return

        for filename in os.listdir(script_dir):
            if filename.endswith(".lua"):
                script_name = filename[:-4]  # remove .lua
                with open(os.path.join(script_dir, filename), "r") as f:
                    lua_code = f.read()
                    self.scripts[script_name] = self.client.register_script(lua_code)
        
        print(f"Loaded {len(self.scripts)} Lua scripts.")

    def run_script(self, script_name: str, keys: List[str] = [], args: List[Any] = []):
        """Execute a registered Lua script"""
        if script_name not in self.scripts:
            raise ValueError(f"Script {script_name} not found")
        try:
            return self.scripts[script_name](keys=keys, args=args)
        except redis.ResponseError as exc:
            code = str(exc)
            if code in {'EINVAL', 'ENOTDIR', 'EISDIR', 'ENOSPC'}:
                raise OSError(getattr(errno, code), os.strerror(getattr(errno, code))) from exc
            raise

    def get_connection(self):
        return self.client
