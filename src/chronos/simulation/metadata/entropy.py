import logging
import random
import time
from typing import Dict, Any

from chronos.simulation.event_bus import WorldTick

logger = logging.getLogger("chronos.simulation.metadata.entropy")

class SystemEntropyPlugin:
    """
    Generates realistic drift in system state for `iostat`, `top`, and `free`.
    Writes these values to Redis so they can be read instantly by the SSH Gateway.
    """
    def __init__(self, redis_client, event_bus):
        self.redis = redis_client
        self.event_bus = event_bus
        
        # Initial State
        self.cpu_usage = 2.0
        self.mem_total = 16384 * 1024 # 16GB in KB
        self.mem_free = 8192 * 1024
        self.mem_cached = 4096 * 1024
        
        self.uptime = 1209600 # 14 days
        
        self.event_bus.subscribe(WorldTick, self.on_tick)
        logger.info("SystemEntropyPlugin initialized")

    def on_tick(self, event: WorldTick):
        self.uptime += event.elapsed_seconds
        
        # Fluctuate CPU slightly
        self.cpu_usage = max(0.1, min(100.0, self.cpu_usage + random.uniform(-1.5, 2.0)))
        
        # Calculate load averages based on CPU
        load1 = (self.cpu_usage / 100.0) * random.uniform(0.8, 1.2)
        load5 = (self.cpu_usage / 100.0) * random.uniform(0.9, 1.1)
        load15 = (self.cpu_usage / 100.0) * random.uniform(0.95, 1.05)
        
        # Leak a tiny bit of memory or let cache grow
        self.mem_cached += int(random.uniform(100, 5000))
        self.mem_free = max(100 * 1024, self.mem_total - self.mem_cached - (2048 * 1024))
        
        # Random IO
        tps = random.uniform(0, 50)
        read_kb = tps * random.uniform(4, 16)
        write_kb = tps * random.uniform(4, 32)
        
        state = {
            "uptime": int(self.uptime),
            "cpu_usage": round(self.cpu_usage, 1),
            "load1": round(load1, 2),
            "load5": round(load5, 2),
            "load15": round(load15, 2),
            "mem_total": self.mem_total,
            "mem_free": self.mem_free,
            "mem_cached": self.mem_cached,
            "io_tps": round(tps, 2),
            "io_read_kb": round(read_kb, 2),
            "io_write_kb": round(write_kb, 2)
        }
        
        try:
            self.redis.hset("env:entropy", mapping=state)
        except Exception as e:
            logger.error(f"Failed to write entropy to Redis: {e}")
