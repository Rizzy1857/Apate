import random
import time
from chronos.simulation.event_bus import EventBus, WorldTick, ServiceStateChanged, EventPriority

class AptServicePlugin:
    def __init__(self, redis_client, event_bus: EventBus):
        self.redis = redis_client
        self.event_bus = event_bus
        self.state = "Idle"
        
        self.event_bus.subscribe(WorldTick, self.on_tick, EventPriority.NORMAL)
        
    def on_tick(self, event: WorldTick):
        old_state = self.state
        if self.state == "Idle":
            if random.random() < 0.05: # 5% chance
                self.state = "Checking"
        elif self.state == "Checking":
            self.state = "Downloading"
        elif self.state == "Downloading":
            self.state = "Installing"
        elif self.state == "Installing":
            self.state = "Idle"
            
        if old_state != self.state:
            self.event_bus.publish(ServiceStateChanged("apt", old_state, self.state, time.time()))
