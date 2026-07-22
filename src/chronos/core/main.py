import sys
import os
import signal
import threading
from fuse import FUSE
from prometheus_client import start_http_server
from chronos.core.state import StateHypervisor
from chronos.interface.fuse import ChronosFUSE
from chronos.core.persistence import PersistenceLayer

def signal_handler(sig, frame):
    print("\n[!] Received shutdown signal, unmounting...")
    sys.exit(0)

def main():
    if len(sys.argv) < 2:
        mount_point = "/mnt/honeypot"
    else:
        mount_point = sys.argv[1]

    print(f"[*] Starting Chronos Core...")
    print(f"[*] Mount point: {mount_point}")

    # 1. Initialize State
    hv = StateHypervisor()
    hv.initialize_filesystem()
    print("[+] State initialized.")
    
    # Initialize DB Schema
    db_layer = PersistenceLayer()
    db_layer.connect()

    # 2. Register Signal Handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 3. Start Metrics Server
    print("[*] Starting Metrics Server on port 8000...")
    start_http_server(8000)

    # 4. Start Watcher Pipeline (audit streamer + evidence collector)
    try:
        from chronos.watcher.log_streamer import AuditLogStreamer
        from chronos.watcher.evidence_collector import EvidenceCollector

        streamer = AuditLogStreamer(db_layer)
        evidence_collector = EvidenceCollector(streamer, db_layer)

        streamer_thread = threading.Thread(target=streamer.start, daemon=True)
        streamer_thread.start()
        print("[+] Watcher pipeline started.")
    except Exception as e:
        print(f"[!] Watcher pipeline failed to start: {e}")

    # 5. Start SSH Gateway (daemon thread — must start before FUSE blocks)
    try:
        from chronos.gateway.ssh_server import SSHHoneypot

        ssh = SSHHoneypot(port=2222)
        ssh_thread = threading.Thread(target=ssh.start, daemon=True)
        ssh_thread.start()
        print("[+] SSH Gateway started on port 2222.")
    except Exception as e:
        print(f"[!] SSH Gateway failed to start: {e}")

    # 6. Mount FUSE (blocks forever — must be last)
    print("[*] Mounting FUSE filesystem (foreground)...")
    try:
        # allow_other is crucial for Docker if accessed from host or other users
        # foreground=True simplifies debugging and signal handling
        FUSE(ChronosFUSE(mount_point), mount_point, foreground=True, allow_other=True)
    except Exception as e:
        print(f"[!] FUSE Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
