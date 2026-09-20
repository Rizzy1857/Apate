"""32 external SSH clients. Run only against the disposable load-test stack."""
import concurrent.futures
import json
import logging
import os
import threading
import time
import uuid

import paramiko
import psycopg2
import redis

logging.getLogger('paramiko').setLevel(logging.CRITICAL)
COUNT = 32
DURATION = int(os.environ.get('APATE_LOAD_SECONDS', '120'))
barrier = threading.Barrier(COUNT, timeout=90)
latencies = []
lock = threading.Lock()
run_id = uuid.uuid4().hex


def prompt(channel):
    data = bytearray()
    channel.settimeout(30)
    while not data.endswith(b'$ '):
        chunk = channel.recv(65536)
        if not chunk:
            raise AssertionError('SSH session closed unexpectedly')
        data.extend(chunk)
        if len(data) > 2 * 1024 * 1024:
            raise AssertionError('Unbounded shell response')
    return data.decode(errors='replace')


def client(index):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    completed = 0
    command = '<session startup>'
    try:
        ssh.connect(os.environ['APATE_CORE_HOST'], port=2222, username='ubuntu',
                    password='synthetic-test', look_for_keys=False, allow_agent=False,
                    timeout=30, banner_timeout=30, auth_timeout=30)
        channel = ssh.invoke_shell()
        prompt(channel)
        barrier.wait()
        deadline = time.monotonic() + DURATION
        while time.monotonic() < deadline and completed < 900:
            token = f'{run_id}-{index}-{completed}'
            command = f'echo {token} > /tmp/probe; cat /tmp/probe; cat /etc/hostname'
            started = time.monotonic()
            channel.sendall((command + '\r').encode())
            output = prompt(channel)
            assert f'{token}\r\nweb01\r\n' in output, output[-400:]
            with lock:
                latencies.append(time.monotonic() - started)
            completed += 1
            time.sleep(0.2)
        return completed
    except Exception as error:
        barrier.abort()
        print(json.dumps({'client_failed': index, 'completed': completed,
                          'command': command, 'error': repr(error)}), flush=True)
        raise
    finally:
        ssh.close()


def main():
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=COUNT) as executor:
        futures = [executor.submit(client, index) for index in range(COUNT)]
        counts = [future.result() for future in futures]
    rd = redis.Redis(host=os.environ['REDIS_HOST'], decode_responses=True)
    conn = psycopg2.connect(host=os.environ['POSTGRES_HOST'], user='chronos',
                            password='chronos_dev_password', dbname='chronos')
    try:
        for _ in range(180):
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM audit_log WHERE operation='ssh_command' AND metadata->>'command' LIKE %s", ('%' + run_id + '%',))
                audited = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM session_evidence WHERE start_time >= to_timestamp(%s)', (started,))
                evidence = cursor.fetchone()[0]
            if audited == sum(counts) and evidence == COUNT and not list(rd.scan_iter(match='session:*:fs:next_inode')):
                break
            time.sleep(1)
        assert audited == sum(counts), (audited, sum(counts))
        assert evidence == COUNT, evidence
        assert not list(rd.scan_iter(match='session_pid:*')), 'Stale PID registrations'
        assert not list(rd.scan_iter(match='session:*:fs:next_inode')), 'Namespace cleanup incomplete'
        ordered = sorted(latencies)
        print(json.dumps({'result': 'PASS', 'sessions': COUNT, 'duration_seconds': DURATION,
                          'commands': sum(counts), 'audited_commands': audited,
                          'session_evidence': evidence, 'latency_p50': ordered[len(ordered)//2],
                          'latency_p95': ordered[int(len(ordered)*.95)],
                          'latency_max': max(ordered), 'run_id': run_id}), flush=True)
    finally:
        conn.close()
        rd.close()


if __name__ == '__main__':
    main()
