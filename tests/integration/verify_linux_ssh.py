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

            def connect(username="ubuntu", *, pkey=None):
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    "127.0.0.1",
                    port=2222,
                    username=username,
                    password=None if pkey else "test",
                    pkey=pkey,
                    look_for_keys=False,
                    allow_agent=False,
                    timeout=10,
                )
                return client

            def rejected_request(action):
                client = connect(username="claimed-intruder")
                try:
                    try:
                        action(client.get_transport())
                    except (paramiko.SSHException, paramiko.ChannelException):
                        return
                    raise AssertionError("SSH request was unexpectedly accepted")
                finally:
                    client.close()

            key_client = connect(
                username="claimed-key-user", pkey=paramiko.RSAKey.generate(2048)
            )
            try:
                try:
                    key_client.exec_command("id", timeout=10)
                except paramiko.SSHException:
                    pass
                else:
                    raise AssertionError("Exec request was unexpectedly accepted")
            finally:
                key_client.close()

            def subsystem(transport):
                channel = transport.open_session(timeout=10)
                channel.invoke_subsystem("sftp")

            rejected_request(subsystem)
            rejected_request(
                lambda transport: transport.open_channel(
                    "direct-tcpip", ("example.invalid", 80), ("127.0.0.1", 42000),
                    timeout=10,
                )
            )
            rejected_request(
                lambda transport: transport.request_port_forward("127.0.0.1", 0)
            )

            channels = []
            for _ in range(2):
                client = connect()
                clients.append(client)
                channel = client.invoke_shell()
                read_prompt(channel)
                channels.append(channel)

            import redis
            control = redis.Redis(host=os.environ['REDIS_HOST'], decode_responses=True)
            from chronos.simulation.world_state import publish_tick
            world = publish_tick(control, seed='integration')
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
            assert f"{world['cpu_usage']} us" in command(0, 'top')
            assert f"{world['mem_free'] // 1024}Mi" in command(0, 'free')
            assert "web01" in command(0, "cat /etc/hostname")
            # Both sessions use the same virtual path and variable name. Each must
            # retain only its own values, including after the peer mutates/removes
            # its copy.
            command(0, "echo alpha-secret > /tmp/secret")
            command(1, "echo beta-secret > /tmp/secret")
            assert "alpha-secret\r\n" in command(0, "cat /tmp/secret")
            assert "beta-secret\r\n" in command(1, "cat /tmp/secret")
            assert "beta-secret" not in command(0, "cat /tmp/secret")
            assert "alpha-secret" not in command(1, "cat /tmp/secret")
            command(1, "rm /tmp/secret")
            assert "alpha-secret\r\n" in command(0, "cat /tmp/secret")
            assert "No such file" in command(1, "cat /tmp/secret")
            assert "secret" in command(0, "ls /tmp")
            assert "secret" not in command(1, "ls /tmp")
            command(0, "export SHARED_NAME=alpha-env")
            command(1, "export SHARED_NAME=beta-env")
            assert "alpha-env\r\n" in command(0, "echo $SHARED_NAME")
            assert "beta-env\r\n" in command(1, "echo $SHARED_NAME")

            # Traversal remains inside the virtual root. Runtime/container paths
            # and procfs are absent from the session namespace.
            assert "No such file" in command(0, "cat /../../app/requirements.txt")
            assert "No such file" in command(0, "cat ../../../../app/requirements.txt")
            assert "No such file" in command(0, "cat /proc/self/status")
            command(0, "cd ../../../../")
            assert "\r\n/\r\n" in command(0, "pwd")
            command(0, "cd /home/ubuntu")

            assert "command not found" in command(0, "bash -c id")
            assert "No such file" in command(0, "cat /app/requirements.txt")
            assert "Permission denied" in command(0, "echo forbidden > /etc/hostname")
            assert "Permission denied" in command(0, "ls /root")
            assert "Permission denied" in command(0, "touch /etc/forbidden")
            assert "Permission denied" in command(0, "mkdir /etc/forbidden")
            assert "Permission denied" in command(0, "rm /etc/hostname")
            assert "Permission denied" in command(0, "cp /tmp/secret /etc/copied")
            assert "Permission denied" in command(0, "mv /tmp/secret /etc/moved")
            assert "alpha-secret\r\n" in command(0, "cat /tmp/secret")
            command(0, "echo owned > /home/ubuntu/note")
            assert "owned\r\n" in command(0, "cat /home/ubuntu/note")
            assert "one\r\n" in command(0, "echo one; echo two")
            stage_output = command(0, "missing | echo recovered")
            assert "command not found" in stage_output and "recovered\r\n" in stage_output
            assert "descriptor" in command(0, "echo hi 2>&1")

            # One contained real-SSH path for every declared command handler.
            assert "/home/ubuntu\r\n" in command(1, "pwd")
            command(1, "export MATRIX_FLAG=matrix-value")
            assert "MATRIX_FLAG=matrix-value" in command(1, "printenv")
            command(1, "unset MATRIX_FLAG")
            assert "MATRIX_FLAG=" not in command(1, "env")
            assert "ubuntu\r\n" in command(1, "whoami")
            assert "ubuntu\r\n" in command(1, "id -un")
            assert "web01\r\n" in command(1, "hostname")
            assert "GNU/Linux" in command(1, "uname -a")
            assert "COMMAND" in command(1, "ps aux")
            assert "Local Address:Port" in command(1, "ss")
            assert "Filesystem" in command(1, "df")
            command(1, "touch /tmp/matrix-file")
            command(1, "echo alpha > /tmp/matrix-file")
            command(1, "echo beta >> /tmp/matrix-file")
            assert "alpha\r\n" in command(1, "head -n 1 /tmp/matrix-file")
            assert "beta\r\n" in command(1, "tail -n 1 /tmp/matrix-file")
            assert "beta\r\n" in command(1, "grep beta /tmp/matrix-file")
            command(1, "echo -x > /tmp/dash-pattern")
            assert "-x\r\n" in command(1, "grep -- -x /tmp/dash-pattern")
            assert "Size:" in command(1, "stat /tmp/matrix-file")
            command(1, "mkdir -p /tmp/matrix-tree/child")
            assert "/tmp/matrix-tree/child" in command(1, "find /tmp/matrix-tree")
            command(1, "cp /tmp/matrix-file /tmp/matrix-copy")
            command(1, "mv /tmp/matrix-copy /tmp/matrix-moved")
            assert "matrix-moved" in command(1, "ls -l /tmp/matrix-moved")
            command(1, "rm /tmp/matrix-moved")
            command(1, "rmdir /tmp/matrix-tree/child")
            command(1, "rmdir /tmp/matrix-tree")
            command(1, "cd /tmp")
            assert "/tmp\r\n" in command(1, "pwd")
            command(1, "cd /home/ubuntu")
            import signal
            worker_sessions = {
                int(key.split(':')[1]): control.get(key)
                for key in control.scan_iter(match='session_pid:*')
            }
            killed_pid = sorted(worker_sessions)[0]
            killed_session = worker_sessions[killed_pid]
            os.kill(killed_pid, signal.SIGKILL)
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
                            rows = [row for row in cursor.fetchall() if row[1]]
                        if (len(rows) >= 2
                                and any("/etc/passwd" in row[2] for row in rows)):
                            break
                        time.sleep(0.1)
                    assert len(rows) >= 2, "No durable command-session evidence"
                    assert any("/etc/passwd" in row[2] for row in rows)
                    assert all(row[0] and row[1] for row in rows)
                    for _ in range(100):
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT metadata->>'outcome', metadata->>'reason' "
                                "FROM audit_log WHERE session_id=%s "
                                "AND operation='ssh_disconnect' ORDER BY id DESC LIMIT 1",
                                (killed_session,),
                            )
                            killed_close = cursor.fetchone()
                        if killed_close:
                            break
                        time.sleep(0.1)
                    assert killed_close == ('interrupted', 'session_error'), killed_close
                    for _ in range(100):
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT metadata FROM audit_log "
                                "WHERE timestamp >= %s AND operation='ssh_request'",
                                (started,),
                            )
                            request_rows = [row[0] for row in cursor.fetchall()]
                        request_types = {row.get('request_type') for row in request_rows}
                        if {'exec', 'subsystem', 'direct_tcpip',
                            'remote_port_forward'} <= request_types:
                            break
                        time.sleep(0.1)
                    assert {'exec', 'subsystem', 'direct_tcpip',
                            'remote_port_forward'} <= request_types, request_types
                    assert all(row.get('accepted') is False for row in request_rows)
                    assert all(row.get('outcome') in ('unsupported', 'denied')
                               for row in request_rows)
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT metadata FROM audit_log "
                            "WHERE timestamp >= %s AND operation='ssh_login' "
                            "AND metadata->>'method'='publickey'",
                            (started,),
                        )
                        public_key_login = cursor.fetchone()
                    assert public_key_login is not None
                    assert public_key_login[0]['claimed_username'] == 'claimed-key-user'
                    assert public_key_login[0]['identity_mismatch'] is True
                    from chronos.watcher.export_report import load_session, write_bundle
                    conn.rollback()
                    observed_command_names = set()
                    for row in rows:
                        events, snapshot = load_session(conn, str(row[0]))
                        with tempfile.TemporaryDirectory() as folder:
                            report = write_bundle(os.path.join(folder, 'bundle'), events,
                                                  {'database_snapshot_at': snapshot})
                        conn.rollback()
                        assert report['commands'], 'Export lost submitted commands'
                        assert not report['unmatched_result_event_ids']
                        assert not report['unmatched_file_event_ids']
                        assert all(command['result_event_ids'] for command in report['commands']), [
                            (command['command'], command['command_id']) for command in report['commands']
                            if not command['result_event_ids']]
                        assert any(command['outcome'] == 'emulated_success'
                                   for command in report['commands'])
                        observed_command_names.update(
                            command['command'].split()[0]
                            for command in report['commands'] if command.get('command')
                        )
                        for recorded in report['commands']:
                            if (recorded['command'] != 'echo hi 2>&1'
                                    and recorded['outcome'] != 'unknown'):
                                assert recorded['stage_results'], recorded['command']
                        compound = next((command for command in report['commands']
                                         if command['command'] == 'missing | echo recovered'), None)
                        if compound is not None:
                            assert compound['exit_status'] == 0
                            assert [stage['exit_status']
                                    for stage in compound['stage_results'][0]['stages']] == [127, 0]
                    declared_handlers = {
                        'cd', 'pwd', 'export', 'env', 'printenv', 'unset', 'echo',
                        'whoami', 'id', 'hostname', 'uname', 'free', 'top', 'ps',
                        'ss', 'df', 'ls', 'cat', 'find', 'grep', 'head', 'tail',
                        'stat', 'touch', 'mkdir', 'rm', 'rmdir', 'cp', 'mv',
                    }
                    assert declared_handlers <= observed_command_names, (
                        declared_handlers - observed_command_names
                    )
                    print('PASS: real database exports reconcile command outcomes and file correlation')
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
