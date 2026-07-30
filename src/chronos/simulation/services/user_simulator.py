import logging
import random
import time

from chronos.simulation.event_bus import WorldTick, CommandSucceeded, CommandStarted

logger = logging.getLogger("chronos.simulation.services.user_simulator")

class UserSimulatorPlugin:
    """
    Simulates background user activity (admins, scripts, automated tasks) by randomly
    publishing CommandStarted and CommandSucceeded events.
    Because of the EventBus architecture, these events automatically trigger log 
    generation in the Auth, Syslog, and Journal plugins!
    """
    def __init__(self, redis_client, event_bus):
        self.redis = redis_client
        self.event_bus = event_bus
        
        self.event_bus.subscribe(WorldTick, self.on_tick)
        logger.info("UserSimulatorPlugin initialized")
        
        self.background_commands = [
            ("root", "apt-get update -y"),
            ("ubuntu", "git pull origin main"),
            ("ubuntu", "vim /home/ubuntu/.bashrc"),
            ("root", "systemctl restart nginx"),
            ("ubuntu", "curl -I https://google.com"),
            ("root", "ufw status"),
            ("ubuntu", "python3 -m pip install requests")
        ]

    def on_tick(self, event: WorldTick):
        # 10% chance per tick to generate a background user command
        if random.random() < 0.10:
            user, cmd = random.choice(self.background_commands)
            session_id = f"simulated_{int(time.time())}"
            ts = time.time() - random.uniform(1, 30) # Happened sometime in the last 30s
            
            # This triggers journalctl and syslog
            self.event_bus.publish(CommandStarted(session_id, cmd, ts))
            
            # This triggers auth.log
            # E.g. sudo commands, or just general success logs
            if user == "root":
                self.event_bus.publish(CommandSucceeded(session_id, cmd, "success", ts + random.uniform(0.1, 2.0)))
