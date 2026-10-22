"""Bounded PostgreSQL-pause test of the GUI-owned collection heartbeat.

The pause is always released by finally; only mirage-gui-db is targeted.
The 16-second observation window allows native UI inspection of degradation.
"""
import json
import subprocess
import time

import redis
from verify_managed_desktop import managed_redis_password


def await_status(client, expected, timeout):
    deadline = time.monotonic() + timeout
    while True:
        state = client.hgetall("chronos:operational_health")
        if state.get("status") == expected:
            return state
        assert time.monotonic() < deadline, (expected, state)
        time.sleep(0.25)


def main():
    client = redis.Redis(password=managed_redis_password(), port=16379, decode_responses=True, socket_timeout=3)
    await_status(client, "healthy", 15)
    subprocess.run(["docker", "pause", "mirage-gui-db"], check=True,
                   stdout=subprocess.DEVNULL, timeout=10)
    try:
        degraded = await_status(client, "degraded", 20)
        print(json.dumps({"phase": "paused", "collection": degraded}), flush=True)
        time.sleep(16)
    finally:
        subprocess.run(["docker", "unpause", "mirage-gui-db"], check=True,
                       stdout=subprocess.DEVNULL, timeout=10)
    restored = await_status(client, "healthy", 20)
    print(json.dumps({"result": "PASS", "restored": restored["status"]}), flush=True)
    client.close()


if __name__ == "__main__":
    main()
