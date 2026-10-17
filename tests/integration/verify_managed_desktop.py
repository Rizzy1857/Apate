"""Exercise only the GUI-owned local stack; keep sessions open for UI review.

Run after launching the GUI. Use --hold to wait for Enter before closing the
two test sessions. The server key is pinned through the local Docker API.
"""
import argparse
import base64
import json
import subprocess
import uuid

import paramiko
import redis


def prompt(channel):
    channel.settimeout(20)
    data = bytearray()
    while not data.endswith(b"$ "):
        chunk = channel.recv(65536)
        assert chunk, "Session closed before prompt"
        data.extend(chunk)
        assert len(data) < 1024 * 1024, "Unbounded response"
    return data.decode(errors="replace")


def execute(channel, command):
    channel.sendall((command + "\n").encode())
    output = prompt(channel)
    lines = output.splitlines(keepends=True)
    if lines and lines[0].strip() == command:
        output = "".join(lines[1:])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()
    networks = json.loads(subprocess.check_output([
        "docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}",
        "mirage-gui-core"], text=True))
    assert len(networks) == 1, "Core must have only the internal network"
    internal = subprocess.check_output([
        "docker", "network", "inspect", "--format", "{{.Internal}}",
        next(iter(networks))], text=True).strip()
    assert internal == "true", "Core network must remain internal"
    bindings = json.loads(subprocess.check_output([
        "docker", "inspect", "--format", "{{json .HostConfig.PortBindings}}",
        "mirage-gui-relay"], text=True))
    assert set(bindings) == {"2222/tcp", "6379/tcp", "5432/tcp"}
    assert all(binding["HostIp"] == "127.0.0.1"
               for entries in bindings.values() for binding in entries)
    public = subprocess.check_output([
        "docker", "exec", "mirage-gui-core", "python3", "-c",
        "import paramiko; print(paramiko.RSAKey(filename='/var/lib/chronos/ssh_host_rsa_key').get_base64())",
    ], text=True).strip()
    key = paramiko.RSAKey(data=base64.b64decode(public))
    clients = []
    control = redis.Redis(host="127.0.0.1", port=16379, decode_responses=True,
                          socket_timeout=3)
    token = "DESKTOP_" + uuid.uuid4().hex
    try:
        channels = []
        for _ in range(2):
            client = paramiko.SSHClient()
            client.get_host_keys().add("[127.0.0.1]:2222", "ssh-rsa", key)
            client.connect("127.0.0.1", port=2222, username="ubuntu",
                           password="scripted-local-test", look_for_keys=False,
                           allow_agent=False, timeout=10)
            clients.append(client)
            channel = client.invoke_shell()
            assert "ubuntu@web01" in prompt(channel)
            channels.append(channel)
        first, second = channels
        assert token in execute(first, f"echo {token} > /tmp/desktop-probe; cat /tmp/desktop-probe")
        assert token not in execute(second, "cat /tmp/desktop-probe")
        assert "/tmp" in execute(first, "cd /tmp; pwd")
        assert "/home/ubuntu" in execute(second, "pwd")
        assert "/app/src" not in execute(first, "ls /app")
        assert "No such file" in execute(first, "cat /proc/self/environ")
        assert "No such file" in execute(first, "cat /../../app/requirements.txt")
        assert execute(first, "cat /etc/hostname").splitlines()[0].strip() == "web01"
        contexts = [control.hgetall(key) for key in control.scan_iter("session:*:context")]
        assert any(row.get("cwd") == "/tmp" for row in contexts)
        assert any(row.get("cwd") == "/home/ubuntu" for row in contexts)
        personas = [control.hgetall(key) for key in control.scan_iter("chronos:device:v1:*")]
        assert personas and all(row.get("device_purpose") for row in personas)
        health = control.hgetall("chronos:operational_health")
        assert health.get("status") == "healthy", health
        jobs = [control.hgetall(key) for key in control.scan_iter("session:*:generation:*")]
        assert any(row.get("path") == "/etc/hostname" and row.get("phase") == "finished" for row in jobs)
        metadata = [control.hgetall(key) for key in control.scan_iter("run:*:fs:blob_meta:*")]
        assert any(row.get("prompt_version") == "2.0-persona" for row in metadata)
        print(json.dumps({"result": "PASS", "sessions": len(clients),
                          "writer_session_id": next(row["session_id"] for row in contexts if row.get("cwd") == "/tmp"),
                          "cross_session_file_isolation": True,
                          "core_internal_network": True,
                          "relay_loopback_only": True,
                          "context_directories": sorted(row["cwd"] for row in contexts),
                          "persistent_personas": len(personas)}), flush=True)
        if args.hold:
            input("Sessions held for GUI review. Press Enter to close.\n")
    finally:
        for client in clients:
            client.close()
        control.close()


if __name__ == "__main__":
    main()
