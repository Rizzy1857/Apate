"""Bounded, non-destructive checks against the GUI-owned local lab.

Pins SSH identity through the local Docker API. Reads the private managed Redis
credential without printing it. Writes only session-local temporary probe files.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import socket
import struct
import subprocess
import time
import uuid

import paramiko
import redis

from verify_managed_desktop import execute, managed_redis_password, prompt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Choose a new results file')
    checks = {}
    public = subprocess.check_output([
        'docker', 'exec', 'mirage-gui-core', 'python3', '-c',
        "import paramiko; print(paramiko.RSAKey(filename='/var/lib/chronos/ssh_host_rsa_key').get_base64())",
    ], text=True).strip()
    key = paramiko.RSAKey(data=base64.b64decode(public))

    def connect():
        client = paramiko.SSHClient()
        client.get_host_keys().add('[127.0.0.1]:2222', key.get_name(), key)
        client.connect('127.0.0.1', port=2222, username='ubuntu', password='local-research-probe',
                       allow_agent=False, look_for_keys=False, timeout=10)
        return client

    with socket.create_connection(('127.0.0.1', 2222), 5) as stream:
        stream.settimeout(5)
        banner = stream.recv(255).decode().strip()
        assert banner == 'SSH-2.0-OpenSSH_9.6p1', banner
        checks['profile_ssh_banner'] = banner
    for operation in ('ping', 'dbsize'):
        unauthenticated = redis.Redis(port=16379, socket_timeout=3)
        try:
            try:
                getattr(unauthenticated, operation)()
            except redis.AuthenticationError:
                checks['redis_unauthenticated_' + operation] = 'rejected'
            else:
                raise AssertionError('Redis accepted unauthenticated ' + operation)
        finally:
            unauthenticated.close()
    control = redis.Redis(port=16379, password=managed_redis_password(),
                          decode_responses=True, socket_timeout=3)
    try:
        assert control.ping()
        checks['redis_authenticated'] = True
        checks['retained_runs_before_probes'] = len(list(control.scan_iter('chronos:run:*')))
        assert control.hget('chronos:operational_health', 'status') == 'healthy'
        checks['collection_healthy'] = True
    finally:
        control.close()
    with socket.create_connection(('127.0.0.1', 15433), 5) as stream:
        stream.settimeout(5)
        payload = struct.pack('!I', 196608) + b'user\x00chronos\x00database\x00chronos\x00\x00'
        stream.sendall(struct.pack('!I', len(payload) + 4) + payload)
        challenge = bytearray()
        while len(challenge) < 9:
            packet = stream.recv(1024)
            assert packet
            challenge.extend(packet)
        assert challenge[0:1] == b'R' and struct.unpack('!I', challenge[5:9])[0] == 10
        checks['postgres_authentication'] = 'SASL required'
    for request in ('exec', 'sftp', 'direct_forward', 'remote_forward'):
        client = connect()
        try:
            transport = client.get_transport()
            try:
                if request == 'exec':
                    transport.open_session(timeout=5).exec_command('id')
                elif request == 'sftp':
                    transport.open_session(timeout=5).invoke_subsystem('sftp')
                elif request == 'direct_forward':
                    transport.open_channel('direct-tcpip', ('127.0.0.1', 6379), ('127.0.0.1', 42000), timeout=5)
                else:
                    transport.request_port_forward('127.0.0.1', 0)
            except paramiko.SSHException:
                checks[request] = 'rejected'
            else:
                raise AssertionError('Unexpectedly accepted ' + request)
        finally:
            client.close()
    client = connect()
    try:
        channel = client.invoke_shell()
        prompt(channel)
        assert execute(channel, 'echo $0').splitlines()[0] == 'bash'
        assert '127' in execute(channel, 'missing-probe; echo $?')
        assert 'not supported' in execute(channel, 'echo $(id)')
        assert execute(channel, 'echo $?').splitlines()[0] == '2'
        checks['shell_identity_and_previous_status'] = True
        for label, overlong in [('ascii', 'A' * 8193), ('utf8', '\u20ac' * 2731)]:
            target = '/tmp/rejected-' + uuid.uuid4().hex
            channel.sendall((overlong + '; echo UNWANTED > ' + target + '\n').encode())
            rejected = prompt(channel)
            assert 'command length limit exceeded' in rejected
            assert not channel.closed
            assert 'No such file' in execute(channel, 'cat ' + target)
            assert execute(channel, 'whoami').splitlines()[0] == 'ubuntu'
            checks['oversized_' + label] = 'rejected; suffix discarded; session usable'
        # Backspace counts UTF-8 bytes, rather than treating a multi-byte character
        # as one byte or leaving the line permanently full after deletion.
        channel.sendall(('echo ' + 'A' * 8184 + '\u20ac\x7fB\n').encode())
        assert 'command length limit exceeded' not in prompt(channel)
        checks['utf8_backspace_at_limit'] = True
        peer = connect()
        target = '/tmp/isolation-' + uuid.uuid4().hex
        try:
            other = peer.invoke_shell()
            prompt(other)
            assert 'ISOLATED' in execute(channel, 'echo ISOLATED > ' + target + '; cat ' + target)
            assert 'No such file' in execute(other, 'cat ' + target)
            execute(channel, 'rm ' + target)
            checks['session_filesystem_isolation'] = True
        finally:
            peer.close()
    finally:
        client.close()

    def concurrent_client(_):
        start = time.monotonic()
        client = connect()
        try:
            channel = client.invoke_shell()
            prompt(channel)
            assert execute(channel, 'whoami').splitlines()[0] == 'ubuntu'
            return round(time.monotonic() - start, 3)
        finally:
            client.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        checks['eight_concurrent_clients_seconds'] = list(pool.map(concurrent_client, range(8)))
    result = {'result': 'PASS', 'checks': checks,
              'limitations': 'Brief local checks; no maximum capacity or undetectability claim.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
