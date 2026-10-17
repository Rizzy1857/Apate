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
from load_state import cleanup_pending, retained_runs

logging.getLogger('paramiko').setLevel(logging.CRITICAL)
COUNT = int(os.environ.get('APATE_LOAD_CLIENTS', '32'))
if COUNT < 1 or COUNT > 32:
    raise ValueError('APATE_LOAD_CLIENTS must be between 1 and 32')
DURATION = int(os.environ.get('APATE_LOAD_SECONDS', '120'))
MAX_COMMANDS = int(os.environ.get('APATE_LOAD_MAX_COMMANDS', '900'))
INTERVAL = float(os.environ.get('APATE_LOAD_INTERVAL', '0.2'))
ROTATE_SECONDS = float(os.environ.get('APATE_LOAD_ROTATE_SECONDS', '3300'))
if DURATION <= 0 or not 0 < ROTATE_SECONDS <= 3300:
    raise ValueError('Duration must be positive; rotation must be in (0, 3300] seconds')
if MAX_COMMANDS < 0:
    raise ValueError('APATE_LOAD_MAX_COMMANDS must be zero or positive')
if INTERVAL < 0:
    raise ValueError('APATE_LOAD_INTERVAL must be nonnegative')
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
        connected_at = time.monotonic()
        session_commands = 0
        sessions = 1
        barrier.wait()
        workload_started = time.monotonic()
        deadline = workload_started + DURATION
        while time.monotonic() < deadline and (MAX_COMMANDS == 0 or completed < MAX_COMMANDS):
            # Sustain the workload across the documented 1h/1000-command limits.
            # Planned rotation is reported separately from unexpected disconnects.
            if time.monotonic() - connected_at >= ROTATE_SECONDS or session_commands >= 800:
                ssh.close()
                ssh.connect(os.environ['APATE_CORE_HOST'], port=2222, username='ubuntu',
                            password='synthetic-test', look_for_keys=False, allow_agent=False,
                            timeout=30, banner_timeout=30, auth_timeout=30)
                channel = ssh.invoke_shell()
                prompt(channel)
                connected_at = time.monotonic()
                session_commands = 0
                sessions += 1
            token = f'{run_id}-{index}-{completed}'
            command = f'echo {token} > /tmp/probe; cat /tmp/probe; cat /etc/hostname'
            started = time.monotonic()
            channel.sendall((command + '\r').encode())
            output = prompt(channel)
            assert f'{token}\r\nweb01\r\n' in output, output[-400:]
            with lock:
                latencies.append(time.monotonic() - started)
            completed += 1
            session_commands += 1
            time.sleep(min(INTERVAL, max(0, deadline - time.monotonic())))
        return {'commands': completed, 'sessions': sessions,
                'elapsed_seconds': time.monotonic() - workload_started}
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
        results = [future.result() for future in futures]
    counts = [result['commands'] for result in results]
    session_count = sum(result['sessions'] for result in results)
    if MAX_COMMANDS == 0:
        assert all(result['elapsed_seconds'] >= DURATION for result in results)
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
            if audited == sum(counts) and evidence == session_count and not cleanup_pending(rd):
                break
            time.sleep(1)
        assert audited == sum(counts), (audited, sum(counts))
        assert evidence == session_count, evidence
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT (submitted.session_id,
                       submitted.metadata->>'command_id'))
                FROM audit_log submitted JOIN audit_log result
                  ON result.session_id = submitted.session_id
                 AND result.metadata->>'command_id' = submitted.metadata->>'command_id'
                WHERE submitted.operation='ssh_command'
                  AND submitted.metadata->>'command' LIKE %s
                  AND result.operation='ssh_command_result'
                  AND result.metadata->>'outcome'='emulated_success'
                  AND result.metadata->>'exit_status'='0'
            """, ('%' + run_id + '%',))
            successful_results, unique_results = cursor.fetchone()
            assert successful_results == unique_results == sum(counts), (
                successful_results, unique_results, sum(counts))
            cursor.execute('SELECT commands FROM session_evidence WHERE start_time >= to_timestamp(%s)', (started,))
            projected = [command for (commands,) in cursor.fetchall() for command in commands]
            assert len(projected) == sum(counts), (len(projected), sum(counts))
            assert all(command.get('outcome') == 'emulated_success' for command in projected)
        assert not list(rd.scan_iter(match='session_pid:*')), 'Stale PID registrations'
        assert not list(rd.scan_iter(match='session:*:fs:next_inode')), 'Namespace cleanup incomplete'
        retention = retained_runs(rd, session_count) if os.environ.get('APATE_LOAD_PERSISTENT_RUNS') == '1' else None
        ordered = sorted(latencies)
        print(json.dumps({'result': 'PASS', 'sessions': session_count, 'concurrent_clients': COUNT,
                          'duration_seconds': DURATION, 'clients': results,
                          'rotation_seconds': ROTATE_SECONDS,
                          'max_commands_per_client': MAX_COMMANDS,
                          'command_interval_seconds': INTERVAL,
                          'commands': sum(counts), 'audited_commands': audited,
                          'successful_results': successful_results,
                          'projected_commands': len(projected),
                          'session_evidence': evidence, 'latency_p50': ordered[len(ordered)//2],
                          'latency_p95': ordered[int(len(ordered)*.95)],
                          'latency_max': max(ordered), 'run_id': run_id,
                          'persistent_run_verification': retention}), flush=True)
    finally:
        conn.close()
        rd.close()


if __name__ == '__main__':
    main()
