import time
from chronos.simulation.event_bus import EventBus, ServiceStateChanged, EventPriority, FileModified

class JournalPlugin:
    def __init__(self, redis_client, event_bus: EventBus):
        self.redis = redis_client
        self.event_bus = event_bus
        
        self.event_bus.subscribe(ServiceStateChanged, self.on_service_change, EventPriority.LOW)
        
    def on_service_change(self, event: ServiceStateChanged):
        # Whenever a service changes state, journal is updated
        self.event_bus.publish(FileModified("/var/log/journal", None, time.time()))
