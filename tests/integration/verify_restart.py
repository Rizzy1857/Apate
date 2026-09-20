"""Fail-closed and audit-retention checks during a disposable service restart."""
import concurrent.futures
import json
import os
import time
import uuid

import paramiko
import psycopg2
import redis

from verify_load import prompt, barrier

COUNT = 32
run_id = uuid.uuid4().hex


def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(os.environ['APATE_CORE_HOST'], port=2222, username='ubuntu',
                password='synthetic-test', look_for_keys=False, allow_agent=False,
                timeout=15, banner_timeout=30, auth_timeout=30)
    channel = ssh.invoke_shell()
    prompt(channel)
    return ssh, channel


def exercise(index):
    ssh, channel = connect()
    confirmed = []
    try:
        barrier.wait()
        for number in range(200):
            command = f'echo {run_id}-{index}-{number} > /tmp/probe; cat /tmp/probe'
            channel.sendall((command + '\r').encode())
            response = prompt(channel)
            if f'{run_id}-{index}-{number}\r\n' not in response:
                # A filesystem failure is allowed; the session must then close.
                assert any(text in response.lower() for text in ('error', 'denied', 'invalid argument')), response
                prompt(channel)
                raise AssertionError('Failed session continued serving commands')
            confirmed.append(command)
            time.sleep(.2)
    except (EOFError, OSError, paramiko.SSHException, AssertionError) as error:
        # Timeouts alone are not a fail-closed result: require actual EOF/closure.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if channel.closed or not ssh.get_transport().is_active():
                break
            channel.settimeout(1)
            try:
                if channel.recv(65536) == b'':
                    break
            except TimeoutError:
                continue
        else:
            raise AssertionError(f'Session {index} hung instead of closing: {error!r}')
    else:
        raise AssertionError('Fault did not terminate the original session')
    finally:
        ssh.close()
    assert confirmed, f'Client {index} did not complete any commands before fault'
    return confirmed


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=COUNT) as pool:
        futures = [pool.submit(exercise, index) for index in range(COUNT)]
        confirmed = [command for future in futures for command in future.result()]
    rd = redis.Redis(host=os.environ['REDIS_HOST'], decode_responses=True,
                     socket_timeout=3, socket_connect_timeout=3)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            if rd.get('test:fault_recovered'):
                break
        except redis.RedisError:
            pass
        time.sleep(1)
    else:
        raise AssertionError('Service did not recover')
    # Wait for old namespaces to be reclaimed, not just for SSH to accept again.
    deadline = time.monotonic() + 180
    while list(rd.scan_iter(match='session:*:fs:next_inode')) and time.monotonic() < deadline:
        time.sleep(1)
    assert not list(rd.scan_iter(match='session:*:fs:next_inode')), 'Orphan namespace leak'
    assert not list(rd.scan_iter(match='session_pid:*')), 'Orphan PID mapping leak'
    ssh, channel = connect()
    try:
        channel.sendall(b'cat /tmp/probe; cat /etc/hostname\r')
        response = prompt(channel)
        assert 'No such file' in response and 'web01\r\n' in response, response
        assert run_id not in response, 'New session inherited old content'
    finally:
        ssh.close()
    conn = psycopg2.connect(host=os.environ['POSTGRES_HOST'], user='chronos',
                            password='chronos_dev_password', dbname='chronos')
    try:
        deadline = time.monotonic() + 60
        while True:
            with conn.cursor() as cursor:
                cursor.execute("SELECT metadata->>'command', event_id FROM audit_log WHERE operation='ssh_command' AND metadata->>'command' LIKE %s", ('%' + run_id + '%',))
                rows = cursor.fetchall()
            if set(confirmed) <= {row[0] for row in rows}:
                break
            assert time.monotonic() < deadline, 'Confirmed command missing from audit'
            time.sleep(1)
        assert len(rows) == len({row[1] for row in rows}), 'Duplicate audit event IDs'
        print(json.dumps({'result': 'PASS', 'fault': os.environ['APATE_LOAD_FAULT'],
                          'sessions': COUNT, 'confirmed_commands': len(confirmed),
                          'audited_commands': len(rows), 'run_id': run_id}), flush=True)
    finally:
        conn.close()
        rd.close()


if __name__ == '__main__':
    main()
