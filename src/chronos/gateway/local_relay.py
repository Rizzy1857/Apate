"""Loopback-published desktop transport; only fixed service destinations.

The dual-network container is not a router or HTTP proxy. Participant input
cannot choose a destination. Core workers remain on the internal network.
"""
import select
import socket
import threading
import time

DESTINATIONS = {2222: ("core-engine", 2222), 6379: ("redis-store", 6379),
                5432: ("db-store", 5432)}
SLOTS = threading.BoundedSemaphore(96)


def forward(client, destination):
    upstream = None
    try:
        upstream = socket.create_connection(destination, timeout=5)
        for stream in (client, upstream):
            stream.settimeout(5)
        deadline = time.monotonic() + 3700
        while time.monotonic() < deadline:
            readable, _, _ = select.select((client, upstream), (), (), 30)
            for source in readable:
                data = source.recv(65536)
                if not data:
                    return
                (upstream if source is client else client).sendall(data)
    except OSError:
        pass
    finally:
        client.close()
        if upstream is not None:
            upstream.close()
        SLOTS.release()


def serve(port):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", port))
        listener.listen(64)
        while True:
            client, _ = listener.accept()
            if not SLOTS.acquire(blocking=False):
                client.close()
                continue
            threading.Thread(target=forward, args=(client, DESTINATIONS[port]),
                             daemon=True).start()


if __name__ == "__main__":
    for port in (6379, 5432):
        threading.Thread(target=serve, args=(port,), daemon=True).start()
    serve(2222)
