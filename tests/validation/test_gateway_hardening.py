"""Regression checks for the live adversarial gateway findings."""
from unittest.mock import Mock

import pytest
import redis

from chronos.gateway import ssh_server as ssh
from chronos.gateway.dispatcher import ASTDispatcher, SessionEnvironment
from chronos.gateway.shell_parser import ShellParser


def test_shell_identity_and_status_preserve_quote_semantics():
    dispatcher = ASTDispatcher(SessionEnvironment())
    parser = ShellParser()
    assert dispatcher.execute_sequence(parser.parse(r"echo $0 '$0' \$0")) == (0, "bash $0 $0\n")
    assert dispatcher.execute_sequence(parser.parse("missing; echo $?")) == (
        0, "bash: missing: command not found\n127\n")
    assert dispatcher.execute_sequence(parser.parse("echo $?")) == (0, "0\n")
    dispatcher.execute_sequence(parser.parse("missing"))
    assert dispatcher.execute_sequence(parser.parse("echo $?")) == (0, "127\n")


def test_application_clients_authenticate_to_password_protected_redis(isolated_redis, monkeypatch):
    from chronos.core.database import Database
    from chronos.watcher.evidence_collector import EvidenceCollector
    from chronos.core.dashboard_metrics_exporter import get_redis_conn

    password = "test-only:@ /%redis"
    isolated_redis.config_set("requirepass", password)
    constructor = redis.Redis
    socket_path = isolated_redis.connection_pool.connection_kwargs['path']

    def local_client(**options):
        assert options['password'] == password
        return constructor(unix_socket_path=socket_path, password=options['password'], decode_responses=True)

    with pytest.raises(redis.AuthenticationError):
        constructor(unix_socket_path=socket_path).ping()
    monkeypatch.setenv('REDIS_PASSWORD', password)
    monkeypatch.setattr(redis, 'Redis', local_client)
    database = Database()
    assert database.client.ping()
    collector = EvidenceCollector(Mock(), Mock())
    assert collector.redis.ping()
    metrics = get_redis_conn()
    assert metrics.ping()
    for client in (database.client, collector.redis, metrics):
        client.close()


@pytest.mark.parametrize('rejected', [b'A' * 8193, ('\u20ac' * 2731).encode()])
def test_ssh_overlong_line_is_audited_drained_and_session_survives(monkeypatch, rejected):
    # Exercise the actual SSH input loop, with only the process/transport boundary
    # replaced. A valid-looking suffix must never reach the command worker.
    payload = rejected + b'; touch /tmp/unwanted\nwhoami\n'
    chunks = iter([payload[i:i+1024] for i in range(0, len(payload), 1024)] + [b''])
    channel = Mock()
    wire = bytearray()
    channel.recv.side_effect = lambda _: next(chunks)
    channel.send.side_effect = lambda data: (wire.extend(data) or len(data))
    transport = Mock()
    transport.accept.return_value = channel
    monkeypatch.setattr(ssh.paramiko, 'Transport', Mock(return_value=transport))
    monkeypatch.setattr(ssh.paramiko, 'RSAKey', Mock())
    # The shell event is normally set by Paramiko before transport.accept returns.
    server = ssh.SSHServer(effective_username='ubuntu')
    server.event.set()
    monkeypatch.setattr(ssh, 'SSHServer', Mock(return_value=server))
    parent = Mock()
    parent.poll.side_effect = lambda timeout=None: timeout in (15, 20)
    parent.recv.side_effect = [{'cwd': '~'}, {'response': 'ubuntu\n', 'returncode': 0, 'cwd': '~'}]
    process = Mock(pid=123)
    process.is_alive.return_value = True
    context = Mock()
    context.Pipe.return_value = (parent, Mock())
    context.Process.return_value = process
    monkeypatch.setattr(ssh.multiprocessing, 'get_context', Mock(return_value=context))
    monkeypatch.setattr(ssh.threading, 'Thread', Mock())
    monkeypatch.setattr(ssh.redis, 'Redis', Mock())
    monkeypatch.setattr(ssh, 'register_lifecycle', Mock())
    monkeypatch.setattr(ssh, 'prepare_disconnect', Mock(return_value=None))
    monkeypatch.delenv('CHRONOS_PERSISTENT_RUNS', raising=False)
    gateway = ssh.SSHHoneypot.__new__(ssh.SSHHoneypot)
    gateway.hostkey_path = '/test/key'
    gateway.audit_log = Mock()
    gateway.handle_client(Mock(), ('127.0.0.1', 10000))
    submissions = [call.args[0] for call in parent.send.call_args_list if isinstance(call.args[0], dict)]
    assert [row['command'] for row in submissions] == ['whoami']
    assert b'command length limit exceeded' in wire
    assert wire.endswith(b'ubuntu@web01:~$ ')
    rejected_events = [call.args[1] for call in gateway.audit_log.call_args_list
                       if call.args[0] == 'ssh_request']
    assert len(rejected_events) == 1
    assert rejected_events[0]['reason'] == 'input_limit'
    assert rejected_events[0]['accepted'] is False
    disconnect = [call.args[1] for call in gateway.audit_log.call_args_list
                  if call.args[0] == 'ssh_disconnect']
    assert disconnect and not any(call.args[0] == 'ssh_command' and 'unwanted' in call.args[1]['command']
                                  for call in gateway.audit_log.call_args_list)
    assert transport.local_version == 'SSH-2.0-OpenSSH_9.6p1'
