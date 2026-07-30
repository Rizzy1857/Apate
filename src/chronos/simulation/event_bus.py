import logging
import json
import threading
from enum import IntEnum
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("chronos.simulation.event_bus")

class EventPriority(IntEnum):
    HIGH = 1    # Synchronous, critical state changes
    NORMAL = 5  # Synchronous, standard operations
    LOW = 10    # Asynchronous, metrics/logs/analytics

# --- Core Events ---

@dataclass
class WorldTick:
    elapsed_seconds: int = 60

@dataclass
class CommandParsed:
    session_id: str
    command_string: str
    timestamp: float

@dataclass
class CommandStarted:
    session_id: str
    command_string: str
    timestamp: float

@dataclass
class CommandSucceeded:
    session_id: str
    command_string: str
    result: str
    timestamp: float

@dataclass
class CommandFailed:
    session_id: str
    command_string: str
    error: str
    timestamp: float

@dataclass
class FileCreated:
    path: str
    session_id: Optional[str] = None
    timestamp: float = 0.0

@dataclass
class FileDeleted:
    path: str
    session_id: Optional[str] = None
    timestamp: float = 0.0

@dataclass
class FileModified:
    path: str
    session_id: Optional[str] = None
    timestamp: float = 0.0

@dataclass
class ServiceStateChanged:
    service_name: str
    old_state: str
    new_state: str
    timestamp: float = 0.0

# Registry for deserialization from Redis
EVENT_TYPES = {
    "WorldTick": WorldTick,
    "CommandParsed": CommandParsed,
    "CommandStarted": CommandStarted,
    "CommandSucceeded": CommandSucceeded,
    "CommandFailed": CommandFailed,
    "FileCreated": FileCreated,
    "FileDeleted": FileDeleted,
    "FileModified": FileModified,
    "ServiceStateChanged": ServiceStateChanged,
}

# --- Event Bus ---

class EventBus:
    def __init__(self, redis_client=None):
        self._subscribers: Dict[type, List[tuple]] = {}
        self._async_executor = ThreadPoolExecutor(max_workers=4)
        self.redis = redis_client
        self._pubsub_thread = None
        self._running = True
        
        if self.redis:
            self._start_redis_listener()
            
    def _start_redis_listener(self):
        def listener():
            pubsub = self.redis.pubsub()
            pubsub.subscribe("chronos:events")
            logger.info("EventBus connected to Redis Pub/Sub channel 'chronos:events'")
            for message in pubsub.listen():
                if not self._running:
                    break
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        event_type_name = payload.get("type")
                        event_data = payload.get("data", {})
                        
                        if event_type_name in EVENT_TYPES:
                            event_class = EVENT_TYPES[event_type_name]
                            event_obj = event_class(**event_data)
                            # Publish locally without forwarding back to Redis
                            self.publish(event_obj, local_only=True)
                    except Exception as e:
                        logger.error(f"Error deserializing event from Redis: {e}")
        
        self._pubsub_thread = threading.Thread(target=listener, daemon=True)
        self._pubsub_thread.start()
        
    def stop(self):
        self._running = False
        self._async_executor.shutdown(wait=False)

    def subscribe(self, event_type: type, callback: Callable, priority: EventPriority = EventPriority.NORMAL):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append((priority, callback))
        # Sort by priority so HIGH executes before NORMAL
        self._subscribers[event_type].sort(key=lambda x: x[0])
        logger.debug(f"Subscribed {callback.__name__} to {event_type.__name__} (Priority: {priority.name})")
        
    def publish(self, event: Any, local_only: bool = False):
        event_type = type(event)
        
        # Publish to Redis if connected and not a local-only bounce
        if self.redis and not local_only:
            try:
                payload = {
                    "type": event_type.__name__,
                    "data": asdict(event)
                }
                self.redis.publish("chronos:events", json.dumps(payload))
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}")
        
        if event_type not in self._subscribers:
            return
            
        for priority, callback in self._subscribers[event_type]:
            if priority == EventPriority.LOW:
                self._async_executor.submit(self._safe_execute, callback, event)
            else:
                self._safe_execute(callback, event)
                
    def _safe_execute(self, callback: Callable, event: Any):
        try:
            callback(event)
        except Exception as e:
            logger.error(f"Error executing event handler {callback.__name__} for event {type(event).__name__}: {e}")
