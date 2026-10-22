"""Three-phase native run-control test: seed, operator resume, operator fresh.

The resume phase deliberately does not arm Redis itself: select the recorded
run using the actual GUI before running it. The record contains synthetic test
data only. No operator data or retained run is deleted.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
import uuid

import paramiko
import redis
from verify_managed_desktop import execute, managed_redis_password, prompt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("seed", "resume", "fresh"))
    parser.add_argument("--record", type=Path, default=Path(".local-deploy/run-verification.json"))
    args = parser.parse_args()
    r = redis.Redis(password=managed_redis_password(), port=16379, decode_responses=True, socket_timeout=3)
    previous = set(r.scan_iter("session:*:context"))
    public = subprocess.check_output(["docker", "exec", "mirage-gui-core", "python3", "-c",
        "import paramiko; print(paramiko.RSAKey(filename='/var/lib/chronos/ssh_host_rsa_key').get_base64())"], text=True).strip()
    client = paramiko.SSHClient()
    client.get_host_keys().add("[127.0.0.1]:2222", "ssh-rsa", paramiko.RSAKey(data=base64.b64decode(public)))
    try:
        client.connect("127.0.0.1", port=2222, username="ubuntu", password="scripted-local-test",
                       allow_agent=False, look_for_keys=False, timeout=10)
        channel = client.invoke_shell()
        prompt(channel)
        keys = set(r.scan_iter("session:*:context")) - previous
        assert len(keys) == 1, "Test requires one newly admitted shell"
        session_id = next(iter(keys)).split(":")[1]
        run_id = r.get(f"session:{session_id}:run_id")
        assert run_id, "Persistent runs must be enabled"
        if args.phase == "seed":
            record = {"run_id": run_id, "token": "RUN_" + uuid.uuid4().hex}
            assert record["token"] in execute(channel, f"echo {record['token']} > /tmp/run-probe; cat /tmp/run-probe; cd /tmp; pwd")
            args.record.parent.mkdir(parents=True, exist_ok=True)
            with args.record.open("x") as output:
                json.dump(record, output, sort_keys=True)
        else:
            record = json.loads(args.record.read_text())
            if args.phase == "resume":
                assert run_id == record["run_id"], "GUI resume selection was not consumed"
                assert "/tmp" in execute(channel, "pwd")
                assert record["token"] in execute(channel, "cat /tmp/run-probe")
            else:
                assert run_id != record["run_id"], "Fresh connection reused an old run"
                assert record["token"] not in execute(channel, "cat /tmp/run-probe")
                assert "/home/ubuntu" in execute(channel, "pwd")
    finally:
        client.close()
    deadline = time.monotonic() + 45
    while r.hget(f"chronos:run:{run_id}", "status") != "paused":
        assert time.monotonic() < deadline, "Closed run was not reconciled/paused"
        time.sleep(0.25)
    print(json.dumps({"result": "PASS", "phase": args.phase, "run_id": run_id,
                      "session_id": session_id, "status": "paused"}), flush=True)
    r.close()


if __name__ == "__main__":
    main()
