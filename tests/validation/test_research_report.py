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


def test_mutation_attempts_failures_and_existing_create_are_not_effects():
    report = build_report([
        event(1, 'ssh_command', command_id='a', command='rm /tmp/x',
              origin='participant'),
        event(2, 'unlink_attempt', command_id='a'),
        event(3, 'unlink_result', command_id='a', outcome='failed', errno=2),
        event(4, 'create_result', command_id='a', outcome='completed', created=False),
        event(5, 'chmod', command_id='a', outcome='completed'),
    ])
    assert [item['operation'] for item in report['commands'][0]['file_events']] == [
        'chmod'
    ]


def test_rejected_ssh_requests_are_separate_and_in_participant_denominator():
    report = build_report([
        event(1, 'ssh_command', command_id='a', command='id', origin='participant',
              claimed_username='root', effective_username='ubuntu',
              identity_mismatch=True,
              identity_policy='accept_any_claim_profile_identity'),
        event(2, 'ssh_command_result', command_id='a', outcome='emulated_success'),
        event(3, 'ssh_request', request_id='r1', request_type='exec', command='uname -a',
              origin='participant', outcome='unsupported', accepted=False),
        event(4, 'ssh_request', request_id='r2', request_type='direct_tcpip',
              origin='scripted_test', outcome='denied', accepted=False),
        event(5, 'ssh_exec', command='legacy'),
    ])
    assert len(report['commands']) == 1
    assert report['commands'][0]['claimed_username'] == 'root'
    assert report['commands'][0]['effective_username'] == 'ubuntu'
    assert report['commands'][0]['identity_mismatch'] is True
    assert len(report['ssh_requests']) == 2
    assert report['ssh_requests'][0]['request_type'] == 'exec'
    assert report['participant_request_outcomes'] == {'unsupported': 1}
    assert report['participant_interaction_outcomes'] == {
        'emulated_success': 1, 'unsupported': 1,
    }
    assert report['legacy_request_event_ids'] == ['5']


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
    assert manifest['artifact_type'] == 'raw_evidence_bundle'
    assert manifest['reproducibility_metadata_complete'] is False
    run_record = json.loads((destination / 'run_record.json').read_text())
    assert set(run_record['missing_reproducibility_fields']) == {
        'run_id', 'source_revision', 'configuration_digest', 'profile_digest'
    }
    assert 'ssh_requests.csv' in manifest['sha256']
    for name, digest in manifest['sha256'].items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
        assert stat.S_IMODE((destination / name).stat().st_mode) == 0o600
    assert 'PRIVATE_COMMAND_SENTINEL' not in (destination / 'report.md').read_text()
    with pytest.raises(FileExistsError):
        write_bundle(destination, [], {})


def test_export_run_record_captures_artifact_treatment(monkeypatch):
    from argparse import Namespace
    import uuid
    from chronos.watcher.export_report import _metadata_from_environment

    monkeypatch.setenv("CHRONOS_ARTIFACT_TREATMENT", "prepared")
    monkeypatch.setenv("CHRONOS_INFERENCE_MODE", "deterministic")
    metadata = _metadata_from_environment(
        Namespace(run_id="run", session_id=uuid.uuid4()), "snapshot"
    )
    assert metadata["artifact_treatment"] == "prepared"
    assert metadata["inference_mode"] == "deterministic"


def test_redacted_export_uses_allowlist_and_never_copies_seeded_free_text(tmp_path):
    import json
    from chronos.watcher.export_report import REDACTION_POLICY, write_bundle

    secret = 'SEEDED-SECRET-7fb0f5d0'
    events = [
        {
            'id': 1, 'session_id': f'session-{secret}', 'operation': 'ssh_command',
            'path': f'/tmp/{secret}',
            'metadata': {
                'command_id': 'command-a', 'command': f'echo {secret}',
                'origin': 'participant', 'claimed_username': secret,
                'arbitrary_nested': {'password': secret},
            },
        },
        {
            'id': 2, 'session_id': f'session-{secret}',
            'operation': 'ssh_command_result',
            'metadata': {
                'command_id': 'command-a', 'outcome': 'emulated_success',
                'exit_status': 0, 'server_elapsed_seconds': 0.1,
            },
        },
    ]
    destination = tmp_path / 'redacted'
    report = write_bundle(destination, events, {
        'run_id': secret,
        'source_revision': secret,
        'configuration_digest': secret,
        'profile_digest': secret,
        'session_id': f'session-{secret}',
    }, mode='redacted')

    for path in destination.iterdir():
        assert secret not in path.read_text()
    manifest = json.loads((destination / 'complete.json').read_text())
    assert manifest['artifact_type'] == 'redacted_evidence_bundle'
    assert manifest['redaction_policy'] == REDACTION_POLICY
    assert manifest['parent_raw_input_sha256']
    disclosure = json.loads((destination / 'redaction.json').read_text())
    assert disclosure['omitted_field_event_counts']['command'] == 1
    assert disclosure['omitted_field_event_counts']['arbitrary_nested'] == 1
    assert report['participant_outcomes'] == {'emulated_success': 1}
    assert report['commands'][0]['command'] is None
    assert report['run_metadata']['reproducibility_metadata_complete'] is True


def test_export_rejects_unknown_mode_without_creating_directory(tmp_path):
    from chronos.watcher.export_report import write_bundle
    destination = tmp_path / 'invalid'
    with pytest.raises(ValueError, match='mode'):
        write_bundle(destination, [], {}, mode='public-ish')
    assert not destination.exists()


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
