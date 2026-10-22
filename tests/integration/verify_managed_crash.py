"""Opt-in destructive-to-test-connection check of the GUI-owned core only.

Requires no other open SSH sessions. Restarts only mirage-gui-core, retains all
volumes, and leaves the synthetic paused run for native operator resume testing.
"""
import base64
import argparse
import json
import subprocess
import time
import uuid

import paramiko
import redis
from verify_managed_desktop import execute, managed_redis_password, prompt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-run')
    parser.add_argument('--token')
    args = parser.parse_args()
    if args.resume_run and not args.token:
        parser.error('--resume-run requires --token')
    control = redis.Redis(password=managed_redis_password(), port=16379, decode_responses=True, socket_timeout=3)
    assert not list(control.scan_iter('session_pid:*')), 'Close other SSH sessions first'
    public = subprocess.check_output([
        'docker', 'exec', 'mirage-gui-core', 'python3', '-c',
        "import paramiko; print(paramiko.RSAKey(filename='/var/lib/chronos/ssh_host_rsa_key').get_base64())",
    ], text=True).strip()
    client = paramiko.SSHClient()
    client.get_host_keys().add('[127.0.0.1]:2222', 'ssh-rsa',
                              paramiko.RSAKey(data=base64.b64decode(public)))
    try:
        client.connect('127.0.0.1', port=2222, username='ubuntu',
                       password='scripted-local-test', allow_agent=False,
                       look_for_keys=False, timeout=10)
        channel = client.invoke_shell()
        prompt(channel)
        contexts = list(control.scan_iter('session:*:context'))
        assert len(contexts) == 1, 'Expected one active context'
        sid = contexts[0].split(':')[1]
        run_id = control.get(f'session:{sid}:run_id')
        assert run_id
        if args.resume_run:
            assert run_id == args.resume_run, 'Native selection was not consumed'
            assert '/tmp' in execute(channel, 'pwd')
            assert args.token in execute(channel, 'cat /tmp/crash-probe')
            print(json.dumps({'result': 'PASS', 'phase': 'native_resume',
                              'run_id': run_id, 'session_id': sid}), flush=True)
            return
        token = 'CRASH_' + uuid.uuid4().hex
        assert token in execute(channel, f'echo {token} > /tmp/crash-probe; cat /tmp/crash-probe; cd /tmp; pwd')
        persona = control.hget(f'chronos:run:{run_id}', 'persona')
        subprocess.run(['docker', 'restart', '--time', '0', 'mirage-gui-core'],
                       check=True, timeout=45, stdout=subprocess.DEVNULL)
        deadline = time.monotonic() + 210
        while control.hget(f'chronos:run:{run_id}', 'status') != 'paused':
            assert time.monotonic() < deadline, 'Crashed run was not reconciled'
            time.sleep(1)
        assert control.hget(f'chronos:run:{run_id}', 'persona') == persona
        assert control.hget(f'chronos:run:{run_id}', 'cwd') == '/tmp'
        assert not control.exists(f'session:{sid}:run_id')
        print(json.dumps({'result': 'PASS', 'run_id': run_id, 'token': token,
                          'session_id': sid, 'status': 'paused',
                          'next_check': 'Native resume; cat /tmp/crash-probe; pwd'}), flush=True)
    finally:
        client.close()
        control.close()


if __name__ == '__main__':
    main()
