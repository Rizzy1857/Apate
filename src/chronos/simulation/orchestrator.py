import threading
import time
import logging
from chronos.simulation.event_bus import EventBus, WorldTick
from chronos.core.state import StateHypervisor

logger = logging.getLogger("chronos.simulation.orchestrator")

class SimulationOrchestrator:
    def __init__(self, db_layer=None):
        self.event_bus = EventBus()
        self.db_layer = db_layer
        
        # We instantiate a StateHypervisor to get access to Redis for the plugins
        self.hv = StateHypervisor()
        
        self._running = False
        self._tick_thread = None
        
    def register_plugins(self):
        """Register all modular simulation plugins."""
        # Ensure plugins module imports are delayed or handled locally 
        # to avoid circular dependencies during initialization.
        from chronos.simulation.metadata.aging import MetadataAgingPlugin
        from chronos.simulation.services.cron import CronServicePlugin
        from chronos.simulation.services.apt import AptServicePlugin
        from chronos.simulation.logs.auth import AuthLogPlugin
        from chronos.simulation.logs.syslog import SyslogPlugin
        from chronos.simulation.logs.journal import JournalPlugin
        
        self.metadata = MetadataAgingPlugin(self.hv.redis, self.event_bus)
        self.cron_service = CronServicePlugin(self.hv.redis, self.event_bus)
        self.apt_service = AptServicePlugin(self.hv.redis, self.event_bus)
        
        self.auth_log = AuthLogPlugin(self.hv.redis, self.event_bus)
        self.syslog = SyslogPlugin(self.hv.redis, self.event_bus)
        self.journal = JournalPlugin(self.hv.redis, self.event_bus)
        
        logger.info("Simulation plugins registered.")
        
    def start(self, tick_interval: int = 60):
        if not self._running:
            self.register_plugins()
            self._running = True
            self._tick_thread = threading.Thread(
                target=self._tick_loop, 
                args=(tick_interval,), 
                daemon=True
            )
            self._tick_thread.start()
            logger.info(f"World Simulation started with {tick_interval}s ticks.")

    def stop(self):
        self._running = False
        if self._tick_thread:
            self._tick_thread.join(timeout=1.0)
            
    def _tick_loop(self, tick_interval: int):
        while self._running:
            time.sleep(tick_interval)
            if not self._running:
                break
            # Publish WorldTick
            self.event_bus.publish(WorldTick(elapsed_seconds=tick_interval))

# Global singleton for easy import across threads
world_simulation = SimulationOrchestrator()
