import time
from chronos.simulation.event_bus import EventBus, WorldTick, EventPriority, FileModified

class SyslogPlugin:
    def __init__(self, redis_client, event_bus: EventBus):
        self.redis = redis_client
        self.event_bus = event_bus
        
        self.event_bus.subscribe(WorldTick, self.on_tick, EventPriority.LOW)
        
    def on_tick(self, event: WorldTick):
        # We can simulate syslog growth
        self.event_bus.publish(FileModified("/var/log/syslog", None, time.time()))
