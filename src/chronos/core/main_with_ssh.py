#!/usr/bin/env python3
"""
Start Chronos with SSH Gateway
Runs both FUSE filesystem and SSH honeypot server
"""

import sys
import os
import threading
import signal

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from chronos.gateway.ssh_server import SSHHoneypot
from chronos.core.state import StateHypervisor
from chronos.interface.fuse import ChronosFUSE
from fuse import FUSE
from prometheus_client import start_http_server

shutdown_flag = threading.Event()

def signal_handler(sig, frame):
    print("\n[!] Received shutdown signal...")
    shutdown_flag.set()
    sys.exit(0)

def start_ssh_server():
    """Start SSH honeypot server in a thread"""
    print("[*] Starting SSH Honeypot on port 2222...")
    honeypot = SSHHoneypot(host="0.0.0.0", port=2222)
    try:
        honeypot.start()
    except Exception as e:
        print(f"[!] SSH server error: {e}")

def main():
    mount_point = sys.argv[1] if len(sys.argv) > 1 else "/mnt/honeypot"

    print(f"[*] Starting Chronos with SSH Gateway...")
    print(f"[*] Mount point: {mount_point}")

    # 1. Initialize State
    hv = StateHypervisor()
    hv.initialize_filesystem()
    print("[+] State initialized.")

    # 2. Register Signal Handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 3. Start Metrics Server
    print("[*] Starting Metrics Server on port 8000...")
    start_http_server(8000)

    # 4. Start SSH Honeypot in background thread
    ssh_thread = threading.Thread(target=start_ssh_server, daemon=True)
    ssh_thread.start()

    # 5. Mount FUSE filesystem (foreground)
    print("[*] Mounting FUSE filesystem (foreground)...")
    fs = ChronosFUSE(hv)
    FUSE(fs, mount_point, nothreads=False, foreground=True, allow_other=True)

if __name__ == "__main__":
    main()
