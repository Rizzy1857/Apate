import sys
import time
import signal
from chronos.simulation.orchestrator import world_simulation
from chronos.core.persistence import PersistenceLayer

def signal_handler(sig, frame):
    print("\n[!] Received shutdown signal, stopping world simulation...")
    world_simulation.stop()
    sys.exit(0)

def main():
    print("[*] Starting World Engine...")
    
    # Initialize DB Layer if needed by plugins (like evidence collector or loggers)
    # The world engine might need persistence to write audit logs from events.
    db_layer = PersistenceLayer()
    db_layer.connect()
    
    # Give orchestrator the db_layer
    world_simulation.db_layer = db_layer
    
    # Register Signal Handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    world_simulation.start(tick_interval=60)
    
    print("[+] World Engine started.")
    
    # Keep the main thread alive while background threads run
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()
