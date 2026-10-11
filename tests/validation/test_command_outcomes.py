"""Submission is evidence of intent, never proof of execution."""
from unittest.mock import Mock

from chronos.watcher.evidence_collector import EvidenceCollector
from chronos.gateway.ssh_server import (
    ChannelWriteError,
    _refresh_session_pid,
    _send_all,
)


class ShortWriteChannel:
    def __init__(self, sizes):
        self.sizes = iter(sizes)
        self.received = bytearray()

    def send(self, payload):
        size = min(next(self.sizes), len(payload))
        self.received.extend(payload[:size])
        return size


def test_send_all_handles_partial_channel_writes():
    channel = ShortWriteChannel([2, 1, 8])
    assert _send_all(channel, b"hello") == 5
    assert bytes(channel.received) == b"hello"


def test_send_all_reports_locally_accepted_bytes_on_disconnect():
    channel = ShortWriteChannel([2, 0])
    try:
        _send_all(channel, b"hello")
    except ChannelWriteError as exc:
        assert exc.bytes_sent == 2
    else:
        raise AssertionError("expected a channel write failure")


def test_worker_attribution_heartbeat_is_owner_fenced():
    client = Mock()
    client.eval.return_value = 1
    assert _refresh_session_pid(client, 123, "session-a", ttl=120) == 1
    script, key_count, key, lifecycle_key, owner, ttl = client.eval.call_args.args
    assert "GET" in script and "EXISTS" in script and "EXPIRE" in script
    assert (key_count, key, lifecycle_key, owner, ttl) == (
        2, "session_pid:123", "session:session-a:lifecycle_recovery",
        "session-a", 120
    )
    client.eval.return_value = 0
    assert _refresh_session_pid(client, 123, "session-b", ttl=120) == 0


def test_worker_attribution_heartbeat_never_resurrects_expired_session(isolated_redis):
    lifecycle_key = "session:session-a:lifecycle_recovery"
    isolated_redis.hset(lifecycle_key, mapping={"operation_id": "operation-a"})

    assert _refresh_session_pid(isolated_redis, 123, "session-a", ttl=120) == 0
    assert isolated_redis.get("session_pid:123") is None
    isolated_redis.setex("session_pid:123", 120, "session-a")
    assert isolated_redis.get("session_pid:123") == "session-a"
    assert _refresh_session_pid(isolated_redis, 123, "session-a", ttl=120) == 1

    assert _refresh_session_pid(isolated_redis, 123, "session-b", ttl=120) == -1
    assert isolated_redis.get("session_pid:123") == "session-a"

    isolated_redis.hset(lifecycle_key, "completed_at", "1")
    assert _refresh_session_pid(isolated_redis, 123, "session-a", ttl=120) == 0
    isolated_redis.delete("session_pid:123", lifecycle_key)
    assert _refresh_session_pid(isolated_redis, 123, "session-a", ttl=120) == 0
    assert isolated_redis.get("session_pid:123") is None


def test_outcomes_require_matching_completion():
    collector = EvidenceCollector(Mock(), Mock())
    evidence = {'commands': [], 'last_successful_interaction': None,
                'first_suspicious_command': None, 'detection_confidence': 0.0}
    collector._get_evidence = Mock(return_value=evidence)
    collector._save_evidence = Mock()
    collector.command_analyzer.analyze = Mock(return_value=Mock(techniques=[], risk_score=0))
    collector.threat_library.match = Mock(return_value=[])

    def emit(operation, metadata):
        collector._process_event({'session_id': 'test', 'timestamp': '2026-09-14T00:00:00',
                                  'operation': operation, 'metadata': metadata})

    emit('ssh_command', {'command': 'whoami', 'command_id': 'a'})
    assert evidence['commands'][0]['outcome'] == 'unknown'
    assert evidence['last_successful_interaction'] is None
    emit('ssh_command_result', {'command_id': 'other', 'outcome': 'emulated_success'})
    assert evidence['last_successful_interaction'] is None
    emit('ssh_command_result', {'command_id': 'a', 'outcome': 'command_failed', 'exit_status': 127})
    assert evidence['last_successful_interaction'] is None
    emit('ssh_command', {'command': 'id', 'command_id': 'b'})
    emit('ssh_command_result', {'command_id': 'b', 'outcome': 'emulated_success', 'exit_status': 0})
    assert evidence['last_successful_interaction'] == '2026-09-14T00:00:00'
    assert evidence['commands'][0]['exit_status'] == 127
    collector.command_analyzer.analyze = Mock(return_value=Mock(techniques=['recon'], risk_score=10))
    for index in range(6):
        emit('ssh_command', {'command': 'id', 'command_id': f'repeat-{index}'})
    assert evidence['detection_confidence'] is None
    assert evidence['detection_status'] == 'detected'
    collector.redis.close()


def test_stage_results_survive_evidence_projection():
    collector = EvidenceCollector(Mock(), Mock())
    evidence = {'commands': [], 'last_successful_interaction': None,
                'first_suspicious_command': None, 'detection_confidence': 0.0}
    collector._get_evidence = Mock(return_value=evidence)
    collector._save_evidence = Mock()
    collector.command_analyzer.analyze = Mock(return_value=Mock(techniques=[], risk_score=0))
    collector.threat_library.match = Mock(return_value=[])
    collector._process_event({
        'session_id': 'stage-test', 'timestamp': '2026-09-29T00:00:00',
        'operation': 'ssh_command',
        'metadata': {'command': 'missing | echo recovered', 'command_id': 'stage-id'},
    })
    stages = [{
        'pipeline_index': 0, 'executed': True, 'exit_status': 0,
        'stages': [
            {'stage_index': 0, 'command': 'missing', 'executed': True, 'exit_status': 127},
            {'stage_index': 1, 'command': 'echo', 'executed': True, 'exit_status': 0},
        ],
    }]
    collector._process_event({
        'session_id': 'stage-test', 'timestamp': '2026-09-29T00:00:01',
        'operation': 'ssh_command_result',
        'metadata': {'command_id': 'stage-id', 'outcome': 'emulated_success',
                     'exit_status': 0, 'stage_results': stages},
    })
    assert evidence['commands'][0]['stage_results'] == stages
    collector.redis.close()


def test_filesystem_audit_links_only_current_session_command():
    from chronos.interface.fuse import ChronosFUSE
    fs = ChronosFUSE.__new__(ChronosFUSE)
    fs.db_layer = Mock()
    fs._control = Mock()
    fs._control.get.side_effect = [b'command-a', b'scripted_test']
    fs._audit('session-a', 'read', '/etc/passwd', 2, {'actual_bytes': 7})
    assert [item.args[0] for item in fs._control.get.call_args_list] == [
        "session:session-a:active_command",
        "session:session-a:active_command_origin",
    ]
    metadata = fs.db_layer.log_operation.call_args.args[-1]
    assert metadata['command_id'] == 'command-a'
    assert metadata['actual_bytes'] == 7
    assert metadata['origin'] == 'scripted_test'
    fs._control.get.side_effect = [None, b'participant']
    fs._audit('session-b', 'read', '/etc/passwd', 2, {})
    metadata = fs.db_layer.log_operation.call_args.args[-1]
    assert metadata['command_id'] is None
    assert metadata['origin'] == 'unattributed'
