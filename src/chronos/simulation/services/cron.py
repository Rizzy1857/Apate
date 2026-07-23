import random
import time
from chronos.simulation.event_bus import EventBus, WorldTick, ServiceStateChanged, EventPriority

class CronServicePlugin:
    def __init__(self, redis_client, event_bus: EventBus):
        self.redis = redis_client
        self.event_bus = event_bus
        self.state = "Idle"
        
        self.event_bus.subscribe(WorldTick, self.on_tick, EventPriority.NORMAL)
        
    def on_tick(self, event: WorldTick):
        old_state = self.state
        if self.state == "Idle":
            if random.random() < 0.2: # 20% chance per tick
                self.state = "Scheduled"
        elif self.state == "Scheduled":
            self.state = "Running"
        elif self.state == "Running":
            self.state = "Finished"
        elif self.state == "Finished":
            self.state = "Idle"
            
        if old_state != self.state:
            self.event_bus.publish(ServiceStateChanged("cron", old_state, self.state, time.time()))
