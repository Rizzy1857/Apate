"""Submission is evidence of intent, never proof of execution."""
from unittest.mock import Mock

from chronos.watcher.evidence_collector import EvidenceCollector


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


def test_filesystem_audit_links_only_current_session_command():
    from chronos.interface.fuse import ChronosFUSE
    fs = ChronosFUSE.__new__(ChronosFUSE)
    fs.db_layer = Mock()
    fs._control = Mock()
    fs._control.get.return_value = b'command-a'
    fs._audit('session-a', 'read', '/etc/passwd', 2, {'actual_bytes': 7})
    fs._control.get.assert_called_once_with('session:session-a:active_command')
    metadata = fs.db_layer.log_operation.call_args.args[-1]
    assert metadata['command_id'] == 'command-a'
    assert metadata['actual_bytes'] == 7
    fs._control.get.return_value = None
    fs._audit('session-b', 'read', '/etc/passwd', 2, {})
    metadata = fs.db_layer.log_operation.call_args.args[-1]
    assert metadata['command_id'] is None
    assert metadata['origin'] == 'unattributed'
