import sys
import os
import signal
from fuse import FUSE
from chronos.core.state import StateHypervisor
from chronos.interface.fuse import ChronosFUSE

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

    # 2. Register Signal Handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 3. Mount FUSE
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
