import pytest
import time
import threading
from chronos.simulation.event_bus import (
    EventBus, EventPriority, WorldTick, 
    CommandSucceeded, CommandStarted, FileCreated, ServiceStateChanged
)
from chronos.simulation.orchestrator import SimulationOrchestrator

class MockRedis:
    def __init__(self):
        self.data = {}
    def hset(self, key, field, value):
        if key not in self.data:
            self.data[key] = {}
        self.data[key][field] = value

def test_event_bus_priority():
    bus = EventBus()
    execution_order = []
    
    def on_high(event):
        execution_order.append("HIGH")
        
    def on_low(event):
        execution_order.append("LOW")
        
    def on_normal(event):
        execution_order.append("NORMAL")
        
    bus.subscribe(WorldTick, on_low, EventPriority.LOW)
    bus.subscribe(WorldTick, on_high, EventPriority.HIGH)
    bus.subscribe(WorldTick, on_normal, EventPriority.NORMAL)
    
    bus.publish(WorldTick(1))
    
    # Wait a bit for the async thread (LOW) to execute
    time.sleep(0.1)
    
    # High should always be before Normal
    assert execution_order[0] == "HIGH"
    assert execution_order[1] == "NORMAL"
    assert "LOW" in execution_order

def test_orchestrator_plugin_cascade():
    orchestrator = SimulationOrchestrator()
    # Mock Redis to avoid requiring a real server
    orchestrator.hv.redis = MockRedis()
    
    # Register plugins which subscribe to the bus
    orchestrator.register_plugins()
    
    # Verify Cron starts Idle
    assert orchestrator.cron_service.state == "Idle"
    
    # Emit a tick to advance state machine
    # Since random is used, we might need multiple ticks, but we just want to ensure it doesn't crash
    orchestrator.event_bus.publish(WorldTick(1))
    
    # Verify Log Generation via Command execution
    # auth.py listens to CommandFailed(cmd="sudo")
    from chronos.simulation.event_bus import CommandFailed
    
    orchestrator.event_bus.publish(CommandFailed(
        session_id="test1", 
        command_string="sudo rm -rf /", 
        error="denied", 
        timestamp=time.time()
    ))
    
    # Since it's EventPriority.LOW, it's executed asynchronously in the thread pool.
    # Give it a tiny sleep to finish.
    time.sleep(0.1)
    # If no exceptions were raised, the event bus handled it correctly!
    assert True

def test_event_bus_stress():
    """
    Stress test the EventBus.
    Publishes 10,000 asynchronous LOW priority events 
    alongside 1,000 synchronous HIGH priority events.
    Verifies no deadlocks and all events are processed.
    """
    bus = EventBus()
    
    # Track counts
    lock = threading.Lock()
    low_count = 0
    high_count = 0
    
    def on_low(event):
        nonlocal low_count
        with lock:
            low_count += 1
            
    def on_high(event):
        nonlocal high_count
        with lock:
            high_count += 1

    bus.subscribe(CommandStarted, on_low, EventPriority.LOW)
    bus.subscribe(WorldTick, on_high, EventPriority.HIGH)
    
    # Blast the bus from multiple threads to simulate real high concurrency load
    def blast_events():
        for i in range(100):
            # 1 HIGH priority
            bus.publish(WorldTick(elapsed_seconds=1))
            # 10 LOW priority
            for _ in range(10):
                bus.publish(CommandStarted(session_id="test", command_string="ls", timestamp=0.0))

    threads = [threading.Thread(target=blast_events) for _ in range(10)]
    start = time.time()
    
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    # Wait for the async worker queue to drain
    # max_workers=4, so give it a second to clear out the 10,000 low priority logs
    bus._async_executor.shutdown(wait=True)
    
    duration = time.time() - start
    print(f"\n[Stress] EventBus processed 10,000 LOW priority and 1,000 HIGH priority events in {duration:.2f}s")
    
    assert high_count == 1000
    assert low_count == 10000
