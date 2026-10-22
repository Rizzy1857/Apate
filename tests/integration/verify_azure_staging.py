"""Smoke-test standalone staging locally; owns only a unique disposable project."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True)
    parser.add_argument('--redis', required=True)
    parser.add_argument('--postgres', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    project = 'mirage-staging-probe-' + uuid.uuid4().hex[:12]
    environment = {**os.environ, 'MIRAGE_IMAGE': args.core,
                   'MIRAGE_REDIS_IMAGE': args.redis,
                   'MIRAGE_POSTGRES_IMAGE': args.postgres,
                   'REDIS_PASSWORD': uuid.uuid4().hex,
                   'POSTGRES_PASSWORD': uuid.uuid4().hex}
    compose = ['docker', 'compose', '-p', project, '-f', str(root / 'compose.azure-staging.yml')]

    def run(command, *, check=True, timeout=180):
        result = subprocess.run(command, env=environment, capture_output=True,
                                text=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout.strip()

    outcome = {'project': project, 'result': 'FAIL', 'images': {
        'core': args.core, 'redis': args.redis, 'postgres': args.postgres}}
    try:
        run(compose + ['config', '--quiet'])
        run(compose + ['up', '-d', '--pull', 'never'])
        for _ in range(60):
            mounted = run(compose + ['exec', '-T', 'core-engine', 'python3', '-c',
                'from chronos.gateway.containment import is_honeypot_mount; print(is_honeypot_mount("/mnt/honeypot"))'], check=False)
            if mounted == 'True':
                break
            time.sleep(1)
        else:
            raise AssertionError('Standalone staging FUSE did not become ready')
        services = {}
        for service in ('core-engine', 'redis-store', 'db-store'):
            cid = run(compose + ['ps', '-q', service])
            assert cid and '\n' not in cid
            data = json.loads(run(['docker', 'inspect', '--format',
                '{{json .HostConfig.PortBindings}}', cid])) or {}
            if service == 'core-engine':
                assert data == {'2222/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '2222'}]}, data
            else:
                assert not data, data
                assert run(['docker', 'inspect', '--format', '{{.Config.User}}', cid]) in ('redis', 'postgres')
            services[service] = {'image': run(['docker', 'inspect', '--format', '{{.Image}}', cid]),
                                 'port_bindings': data}
        probe = r'''
import json, os, uuid
import paramiko, psycopg2, redis
r = redis.Redis(host='redis-store', password=os.environ['REDIS_PASSWORD'])
assert r.ping()
try:
    redis.Redis(host='redis-store').ping()
except redis.AuthenticationError:
    pass
else:
    raise AssertionError('Unauthenticated Redis accepted')
try:
    psycopg2.connect(host='db-store', dbname='chronos', user='chronos', password='incorrect-probe-password', connect_timeout=3)
except psycopg2.OperationalError as error:
    assert 'password authentication failed' in str(error)
else:
    raise AssertionError('Incorrect PostgreSQL password accepted')
assert os.environ['CHRONOS_PERSISTENT_RUNS'] == '1'
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Disposable in-container loopback only.
client.connect('127.0.0.1', port=2222, username='ubuntu', password='synthetic-test', look_for_keys=False, allow_agent=False, timeout=10)
try:
    channel = client.invoke_shell()
    channel.settimeout(20)
    def prompt():
        output = b''
        while not output.endswith(b'$ '):
            block = channel.recv(65536)
            assert block and len(output) < 262144
            output += block
        return output.decode()
    prompt()
    token = uuid.uuid4().hex
    channel.sendall(('echo ' + token + ' > /tmp/staging-probe; cat /tmp/staging-probe; cd /../../; pwd; cat /etc/hostname\r').encode())
    assert token + '\r\n/\r\nweb01\r\n' in prompt()
finally:
    client.close()
print(json.dumps({'ssh_fake_filesystem': True, 'root_clamped': True, 'redis_authentication': True, 'postgres_authentication': True, 'persistent_runs_enabled': True}))
'''
        outcome.update(json.loads(run(compose + ['exec', '-T', 'core-engine', 'python3', '-c', probe])))
        outcome.update(result='PASS', services=services)
    except BaseException as error:
        outcome['error'] = repr(error)
        raise
    finally:
        try:
            (args.output / 'core.log').write_text(run(compose + ['logs', '--no-color', 'core-engine'], check=False))
        finally:
            cleanup = subprocess.run(compose + ['down', '--volumes', '--remove-orphans'],
                                     env=environment, capture_output=True, text=True, timeout=120)
            outcome['cleanup_succeeded'] = cleanup.returncode == 0
            if cleanup.returncode:
                outcome['result'] = 'FAIL'
            (args.output / 'result.json').write_text(json.dumps(outcome, indent=2) + '\n')
            if cleanup.returncode:
                raise RuntimeError('Disposable staging cleanup failed: ' + cleanup.stderr)
    print(json.dumps(outcome, indent=2))


if __name__ == '__main__':
    main()
