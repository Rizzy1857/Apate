import sys
import os
import threading
import signal
import argparse
from fuse import FUSE
from prometheus_client import start_http_server
from chronos.core.state import StateHypervisor
from chronos.interface.fuse import ChronosFUSE
from chronos.gateway.ssh_server import SSHHoneypot


def signal_handler(sig, frame):
    print("\n[!] Received shutdown signal...")
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
    parser = argparse.ArgumentParser(
        description="Chronos Honeypot Framework",
        prog="chronos"
    )
    parser.add_argument(
        "mount_point",
        nargs="?",
        default="/mnt/honeypot",
        help="FUSE mount point (default: /mnt/honeypot)"
    )
    parser.add_argument(
        "--gateway",
        choices=["none", "ssh"],
        default="none",
        help="Enable gateway services (default: none)"
    )

    args = parser.parse_args()
    mount_point = args.mount_point

    print(f"[*] Starting Chronos...")
    print(f"[*] Mount point: {mount_point}")
    if args.gateway:
        print(f"[*] Gateway mode: {args.gateway}")

    # Initialize State
    hv = StateHypervisor()
    hv.initialize_filesystem()
    print("[+] State initialized.")

    # Register Signal Handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start Metrics Server
    print("[*] Starting Metrics Server on port 8000...")
    start_http_server(8000)

    # Start SSH Gateway if requested
    if args.gateway == "ssh":
        ssh_thread = threading.Thread(target=start_ssh_server, daemon=True)
        ssh_thread.start()

    # Mount FUSE filesystem
    print("[*] Mounting FUSE filesystem...")
    try:
        fs = ChronosFUSE(hv)
        FUSE(fs, mount_point, nothreads=False, foreground=True, allow_other=True)
    except Exception as e:
        print(f"[!] FUSE Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
