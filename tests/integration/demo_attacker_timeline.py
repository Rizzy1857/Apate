"""Create a paced, synthetic attacker session on the GUI-owned local honeypot.

Run with .venv/bin/python tests/integration/demo_attacker_timeline.py.
Only the pinned local SSH emulator is contacted; commands run in its fake filesystem.
"""
import base64
import json
import subprocess
import time
from datetime import datetime, timezone

import paramiko
import redis

from verify_managed_desktop import execute, managed_redis_password, prompt


PHASES = [
    ("Host discovery", [
        "whoami", "id", "pwd", "hostname", "uname -a", "cat /etc/os-release",
        "date", "uptime", "ls -la /", "ps aux", "env",
    ]),
    ("Account and service discovery", [
        "cat /etc/passwd", "cat /etc/group", "ls -la /home", "ls -la /root",
        "sudo -l", "cat /etc/sudoers", "cat /etc/shadow", "ls -la /etc/ssh",
        "cat /etc/ssh/sshd_config", "ss -tulpn", "ip addr", "cat /etc/hosts",
    ]),
    ("Application and credential exploration", [
        "ls -la /var/www", "ls -la /var/www/html", "find /var/www -name '*.conf'",
        "grep -r password /var/www", "ls -la /home/ubuntu/.ssh",
        "cat /home/ubuntu/.ssh/authorized_keys", "cat /home/ubuntu/.bash_history",
        "ls -la /var/backups", "ls -la /var/log", "cat /var/log/auth.log",
    ]),
    ("Synthetic collection in the fake filesystem", [
        "mkdir -p /tmp/timeline-demo", "cd /tmp/timeline-demo", "pwd",
        "echo synthetic-demo-only > README.txt", "cat README.txt",
        "cp /etc/passwd /tmp/timeline-demo/accounts.txt", "ls -la",
        "cat accounts.txt", "wc -l accounts.txt", "ls -la /etc/cron.d",
        "crontab -l", "history", "cd /home/ubuntu", "pwd",
    ]),
]


def main():
    public = subprocess.check_output([
        "docker", "exec", "mirage-gui-core", "python3", "-c",
        "import paramiko; print(paramiko.RSAKey(filename='/var/lib/chronos/ssh_host_rsa_key').get_base64())",
    ], text=True).strip()
    control = redis.Redis(host="127.0.0.1", port=16379,
                          password=managed_redis_password(), decode_responses=True,
                          socket_timeout=3)
    before = set(control.scan_iter("session:*:context"))
    client = paramiko.SSHClient()
    client.get_host_keys().add("[127.0.0.1]:2222", "ssh-rsa",
                              paramiko.RSAKey(data=base64.b64decode(public)))
    marker = "TIMELINE_DEMO_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        client.connect("127.0.0.1", port=2222, username="ubuntu",
                       password="synthetic-timeline-demo", look_for_keys=False,
                       allow_agent=False, timeout=10)
        channel = client.invoke_shell()
        prompt(channel)
        execute(channel, "echo " + marker)
        session_ids = [control.hget(key, "session_id") for key in
                       set(control.scan_iter("session:*:context")) - before]
        print(json.dumps({"marker": marker, "session_ids": session_ids}), flush=True)
        count = 1
        for phase, commands in PHASES:
            print(phase, flush=True)
            for command in commands:
                execute(channel, command)
                count += 1
                time.sleep(1.2)
            print(f"  {count} actions recorded", flush=True)
            time.sleep(2)
        channel.sendall(b"exit\n")
        print(json.dumps({"marker": marker, "actions_sent": count,
                          "session_ids": session_ids, "status": "SSH interaction complete"}), flush=True)
    finally:
        client.close()
        control.close()


if __name__ == "__main__":
    main()
