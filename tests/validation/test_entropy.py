import pytest
import time
from chronos.simulation.event_bus import EventBus, WorldTick, CommandStarted
from chronos.simulation.metadata.entropy import SystemEntropyPlugin
from chronos.simulation.services.user_simulator import UserSimulatorPlugin

class MockRedis:
    def __init__(self):
        self.data = {}
    def hset(self, key, mapping):
        if key not in self.data:
            self.data[key] = {}
        for k, v in mapping.items():
            self.data[key][k] = str(v)
    def hgetall(self, key):
        return self.data.get(key, {})

def test_system_entropy_plugin():
    redis = MockRedis()
    bus = EventBus()
    
    # We do not start the redis listener thread because redis is a mock
    # and we just want to test the plugin logic synchronously.
    
    plugin = SystemEntropyPlugin(redis, bus)
    
    assert plugin.uptime == 1209600
    
    # Simulate 5 ticks
    for _ in range(5):
        bus.publish(WorldTick(elapsed_seconds=60))
        # wait for async pool to execute if Priority is low, but WorldTick is NORMAL/HIGH
        # actually in SystemEntropyPlugin it's NORMAL by default
        time.sleep(0.01)
        
    state = redis.hgetall("env:entropy")
    assert state, "State was not written to Redis"
    assert int(state["uptime"]) == 1209600 + (60 * 5)
    assert float(state["cpu_usage"]) > 0
    assert float(state["io_tps"]) >= 0

def test_user_simulator_plugin():
    redis = MockRedis()
    bus = EventBus()
    
    plugin = UserSimulatorPlugin(redis, bus)
    
    # We want to capture CommandStarted events
    commands_seen = []
    def on_command_started(event: CommandStarted):
        commands_seen.append(event)
        
    bus.subscribe(CommandStarted, on_command_started)
    
    # Tick many times to trigger the 10% chance
    for _ in range(100):
        bus.publish(WorldTick(60))
        time.sleep(0.001)
        
    # We should have seen roughly 10 commands (since 10%)
    assert len(commands_seen) > 0, "UserSimulator did not emit any commands"
    assert commands_seen[0].command_string != ""
