import logging
from enum import IntEnum
from dataclasses import dataclass, field
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

# --- Event Bus ---

class EventBus:
    def __init__(self):
        self._subscribers: Dict[type, List[tuple]] = {}
        self._async_executor = ThreadPoolExecutor(max_workers=4)
        
    def subscribe(self, event_type: type, callback: Callable, priority: EventPriority = EventPriority.NORMAL):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append((priority, callback))
        # Sort by priority so HIGH executes before NORMAL
        self._subscribers[event_type].sort(key=lambda x: x[0])
        logger.debug(f"Subscribed {callback.__name__} to {event_type.__name__} (Priority: {priority.name})")
        
    def publish(self, event: Any):
        event_type = type(event)
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
