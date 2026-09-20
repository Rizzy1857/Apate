import time
from chronos.simulation.event_bus import EventBus, CommandFailed, EventPriority, FileModified

class AuthLogPlugin:
    def __init__(self, redis_client, event_bus: EventBus):
        self.redis = redis_client
        self.event_bus = event_bus
        
        self.event_bus.subscribe(CommandFailed, self.on_command_failed, EventPriority.LOW)
        
    def on_command_failed(self, event: CommandFailed):
        if "sudo" in event.command_string:
            # Simulate updating auth.log metadata
            # In a full simulation, we might actually append lines to a Redis key
            # For now, we emit a FileModified event to touch the file
            self.event_bus.publish(FileModified("/var/log/auth.log", event.session_id, time.time()))
