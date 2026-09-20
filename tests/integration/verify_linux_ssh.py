"""Run inside a disposable Linux container with /dev/fuse and a disposable Redis.

Exercises the real kernel mount and persistent SSH session worker processes.
No live LLM or PostgreSQL is required; generation uses deterministic files.
"""

import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

import paramiko
from chronos.gateway.containment import is_honeypot_mount


def read_prompt(channel):
    output = b""
    channel.settimeout(25)
    while not output.endswith(b"$ "):
        block = channel.recv(65536)
        if not block:
            raise AssertionError(f"Channel closed: {output!r}")
        output += block
    return output.decode()


def main():
    started = datetime.utcnow()
    clients = []
    with tempfile.TemporaryFile() as log:
        core = subprocess.Popen(
            [sys.executable, "-m", "chronos.core.main"], stdout=log, stderr=log
        )
        try:
            for _ in range(150):
                if core.poll() is not None:
                    raise AssertionError("Core exited before mount")
                if is_honeypot_mount("/mnt/honeypot"):
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("FUSE mount not ready")
            channels = []
            for _ in range(2):
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    "127.0.0.1",
                    port=2222,
                    username="ubuntu",
                    password="test",
                    look_for_keys=False,
                    allow_agent=False,
                    timeout=10,
                )
                clients.append(client)
                channel = client.invoke_shell()
                read_prompt(channel)
                channels.append(channel)

            import redis
            control = redis.Redis(host=os.environ['REDIS_HOST'], decode_responses=True)
            for key in control.scan_iter(match='session_pid:*'):
                pid = key.split(':')[1]
                with open(f'/proc/{pid}/status') as status_file:
                    status = dict(line.split(':', 1) for line in status_file if ':' in line)
                assert status['Uid'].split() == ['1000'] * 4
                assert int(status['CapEff'].strip(), 16) == 0
                assert status['NoNewPrivs'].strip() == '1'
                assert status['Seccomp'].strip() == '2'

            def command(index, text):
                channels[index].sendall((text + "\r").encode())
                result = read_prompt(channels[index])
                print(repr(result), flush=True)
                return result

            assert "ubuntu:x:1000:" in command(0, "cat /etc/passwd")
            assert "web01" in command(0, "cat /etc/hostname")
            command(0, "echo private-data > /tmp/secret")
            assert "private-data\r\n" in command(0, "cat /tmp/secret")
            assert "No such file" in command(1, "cat /tmp/secret")
            command(0, "echo x > /tmp/secret")
            assert "private-data" not in command(0, "cat /tmp/secret")
            assert "command not found" in command(0, "bash -c id")
            assert "No such file" in command(0, "cat /app/requirements.txt")
            assert "Permission denied" in command(0, "echo forbidden > /etc/hostname")
            assert "Permission denied" in command(0, "ls /root")
            command(0, "echo owned > /home/ubuntu/note")
            assert "owned\r\n" in command(0, "cat /home/ubuntu/note")
            assert "Permission denied" in command(0, "mkdir /etc/forbidden")
            assert "one\r\n" in command(0, "echo one; echo two")
            import signal
            worker_pids = sorted(int(key.split(':')[1]) for key in control.scan_iter(match='session_pid:*'))
            os.kill(worker_pids[0], signal.SIGKILL)
            channels[0].sendall(b'echo after-worker-death\r')
            try:
                read_prompt(channels[0])
            except AssertionError as exc:
                assert 'Channel closed' in str(exc)
            else:
                raise AssertionError('Dead worker session did not close')
            assert 'survivor\r\n' in command(1, 'echo survivor')
            print('PASS: forcibly killed worker closes its session; other session remains functional')
            print(
                "PASS: real Linux SSH/FUSE, deterministic generation, session isolation, truncation, execution boundary"
            )
            for client in clients:
                client.close()
            if os.environ.get("CHRONOS_TEST_AUDIT") == "1":
                import psycopg2

                conn = psycopg2.connect(
                    host=os.environ["POSTGRES_HOST"],
                    user="chronos",
                    password="chronos_dev_password",
                    dbname="chronos",
                )
                try:
                    for _ in range(100):
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT session_id, commands, visited_files FROM session_evidence WHERE start_time >= %s",
                                (started,),
                            )
                            rows = cursor.fetchall()
                        if len(rows) >= 2:
                            break
                        time.sleep(0.1)
                    assert len(rows) >= 2, "No durable session evidence"
                    assert any("/etc/passwd" in row[2] for row in rows)
                    assert all(row[0] and row[1] for row in rows)
                    print(
                        "PASS: session-tagged file operations and command evidence persisted in PostgreSQL"
                    )
                finally:
                    conn.close()
        finally:
            for client in clients:
                client.close()
            core.terminate()
            try:
                core.wait(timeout=5)
            except subprocess.TimeoutExpired:
                core.kill()
                core.wait()
            log.seek(0)
            print(log.read().decode(errors="replace")[-12000:])


if __name__ == "__main__":
    main()
