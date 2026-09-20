import pytest
from chronos.watcher.research_report import build_report


def event(identifier, operation, **metadata):
    return {'id': identifier, 'session_id': 'session', 'operation': operation,
            'metadata': metadata}


def test_reconcile_replay_out_of_order_missing_and_synthetic():
    submitted = event(1, 'ssh_command', command_id='a', command='id', origin='participant')
    events = [
        event(2, 'ssh_command_result', command_id='a', outcome='emulated_success',
              exit_status=0, server_elapsed_seconds=.25),
        submitted, submitted,
        event(3, 'ssh_command', command_id='b', command='cat x', origin='participant'),
        event(4, 'ssh_command', command_id='c', origin='synthetic'),
        event(5, 'ssh_command_result', command_id='c', outcome='emulated_success',
              server_elapsed_seconds=100),
        event(6, 'read', command_id='a', actual_bytes=10),
    ]
    report = build_report(events)
    assert report['duplicate_events_removed'] == 1
    assert report['participant_outcomes'] == {'emulated_success': 1, 'unknown': 1}
    assert report['participant_server_latency']['p95_seconds'] == .25
    assert report['participant_server_latency']['sample_count'] == 1
    assert report['commands'][0]['file_events'][0]['event_id'] == '6'
    assert build_report(reversed(events))['input_sha256'] == report['input_sha256']


def test_conflicts_and_legacy_are_not_success():
    report = build_report([
        event(1, 'ssh_command', command='legacy'),
        event(2, 'ssh_command', command_id='a', origin='participant'),
        event(3, 'ssh_command_result', command_id='a', outcome='emulated_success'),
        event(4, 'ssh_command_result', command_id='a', outcome='command_failed'),
    ])
    assert report['legacy_submission_event_ids'] == ['1']
    assert report['participant_outcomes'] == {'unknown': 1}
    assert report['commands'][0]['conflicting_results']
    with pytest.raises(ValueError):
        build_report([event(1, 'read'), event(1, 'write')])


def test_private_export_hashes_and_no_overwrite(tmp_path):
    import hashlib
    import json
    import stat
    from chronos.watcher.export_report import write_bundle
    destination = tmp_path / 'evidence'
    write_bundle(destination, [event(1, 'ssh_command', command_id='a',
                                    command='PRIVATE_COMMAND_SENTINEL', origin='participant')], {})
    assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    manifest = json.loads((destination / 'complete.json').read_text())
    for name, digest in manifest['sha256'].items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
        assert stat.S_IMODE((destination / name).stat().st_mode) == 0o600
    assert 'PRIVATE_COMMAND_SENTINEL' not in (destination / 'report.md').read_text()
    with pytest.raises(FileExistsError):
        write_bundle(destination, [], {})


def test_snapshot_export_uses_readonly_transaction_and_bound_session():
    from datetime import datetime, timezone
    from unittest.mock import MagicMock
    from chronos.watcher.export_report import load_session
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    timestamp = datetime.now(timezone.utc)
    cursor.fetchone.return_value = {'snapshot_at': timestamp}
    cursor.__iter__.return_value = iter([{'id': 1, 'timestamp': timestamp}])
    session = '12345678-1234-1234-1234-123456789012'
    events, snapshot = load_session(connection, session)
    connection.set_session.assert_called_once_with(
        isolation_level='REPEATABLE READ', readonly=True, autocommit=False)
    assert cursor.execute.call_args.args[1] == (session,)
    assert events[0]['timestamp'] == snapshot
