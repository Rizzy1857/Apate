import json
import os
import subprocess
import sys
import uuid
from unittest.mock import Mock

import pytest
import redis

from chronos.core.audit_spool import AuditSpool
from chronos.core.session_cleanup import orphan_sessions, delete_namespace
from chronos.core.scoped_redis import ScopedRedis
from chronos.core.content import mutate_content, read_blob
from chronos.gateway.dispatcher import SessionEnvironment, CommandRegistry
from chronos.intelligence.orchestrator import GenerationOrchestrator
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.gateway.ssh_server import SSHServer
from chronos.intelligence.inference import InferenceRuntime, ModelUnreachableError
from test_hardening import hypervisor


def test_outbox_survives_abrupt_process_exit(tmp_path):
    path = str(tmp_path / 'audit.sqlite3')
    script = ('import os,sys; from chronos.core.audit_spool import AuditSpool; '
              's=AuditSpool(sys.argv[1]); s.append(["durable"]); os._exit(17)')
    result = subprocess.run([sys.executable, '-c', script, path], check=False)
    assert result.returncode == 17
    spool = AuditSpool(path, max_events=1)
    pending = spool.pending()
    assert len(pending) == 1 and pending[0][1] == ['durable']
    with pytest.raises(RuntimeError, match='full'):
        spool.append(['lost'])
    assert spool.pending() == pending
    spool.acknowledge([pending[0][0]])
    assert spool.pending() == []
    spool.append(['next'])
    spool.close()
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_outbox_rejects_large_events(tmp_path):
    spool = AuditSpool(str(tmp_path / 'audit.sqlite3'))
    with pytest.raises(RuntimeError, match='64 KiB'):
        spool.append(['x' * 65536])
    assert spool.pending() == []
    spool.close()


def test_password_not_recorded(caplog):
    callback = Mock()
    server = SSHServer(audit_callback=callback)
    server.check_auth_password('ubuntu', 'not-for-logs')
    assert 'not-for-logs' not in repr(callback.call_args)
    assert 'not-for-logs' not in caplog.text


def test_orphan_recovery_preserves_live_and_unrelated_state(isolated_redis):
    r = isolated_redis
    live, dead = str(uuid.uuid4()), str(uuid.uuid4())
    for sid in (live, dead):
        r.set(f'session:{sid}:fs:next_inode', 2)
        r.set(f'session:{sid}:fs:blob:private', 'bytes')
        r.set(f'chronos:machine_state:{sid}', 'state')
    r.set('unrelated', 'keep')
    r.set('session_pid:123', live)
    assert orphan_sessions(r) == {dead}
    delete_namespace(r, dead)
    assert r.get(f'session:{live}:fs:blob:private') == 'bytes'
    assert not list(r.scan_iter(match=f'session:{dead}:*'))
    assert r.get('unrelated') == 'keep'
    r.delete('session_pid:123')
    assert orphan_sessions(r) == {live}
    with pytest.raises(ValueError):
        delete_namespace(r, '*')


def test_manifest_partial_recovery_and_permissions(isolated_redis):
    client = ScopedRedis(isolated_redis, 'session:recovery:')
    hv = hypervisor(client)
    hv.initialize_filesystem()
    links = client.hget('fs:inode:1', 'nlink')
    inode = hv._resolve_path_sync('/etc/passwd')
    client.hset(f'fs:inode:{inode}', 'content_state', 'ready')
    client.delete('fs:initialized')
    hv.initialize_filesystem()
    assert client.hget('fs:inode:1', 'nlink') == links
    assert client.hget(f'fs:inode:{inode}', 'content_state') == 'ready'
    home = hv._resolve_path_sync('/home/ubuntu')
    assert client.hget(f'fs:inode:{home}', 'uid') == '1000'
    tmp = hv._resolve_path_sync('/tmp')
    assert int(client.hget(f'fs:inode:{tmp}', 'mode')) & 0o7777 == 0o1777


def test_cleanup_redis_outage_does_not_assume_everyone_dead():
    client = Mock()
    client.scan_iter.side_effect = redis.ConnectionError('offline')
    with pytest.raises(redis.ConnectionError):
        orphan_sessions(client)
    client.delete.assert_not_called()


def test_evidence_survives_redis_cache_loss(isolated_redis):
    from chronos.watcher.evidence_collector import EvidenceCollector
    class DurableProgress:
        def __init__(self):
            self.data = {}
        def load_evidence_progress(self, sid):
            return json.loads(self.data[sid]) if sid in self.data else None
        def save_evidence_progress(self, sid, data):
            self.data[sid] = json.dumps(data)
        def flush_evidence(self, sid, data):
            self.final = data
            return True
    persistence = DurableProgress()
    collector = EvidenceCollector(Mock(), persistence)
    collector.redis.close()
    collector.redis = isolated_redis
    sid = str(uuid.uuid4())
    collector._process_event({'id': 1, 'session_id': sid, 'timestamp': '2026-09-09T00:00:00',
                             'operation': 'ssh_command', 'metadata': {'command': 'id'}})
    isolated_redis.delete(f'chronos:evidence:{sid}')
    collector._process_event({'id': 2, 'session_id': sid, 'timestamp': '2026-09-09T00:00:01',
                             'operation': 'ssh_disconnect'})
    assert persistence.final['commands'][0]['command'] == 'id'
    collector._process_event({'id': 2, 'session_id': sid, 'timestamp': '2026-09-09T00:00:01',
                             'operation': 'ssh_disconnect'})
    assert len(persistence.final['commands']) == 1


def test_command_errors_and_output_budget(tmp_path):
    (tmp_path / 'note').write_bytes(b'a\nb\nc\n')
    commands = CommandRegistry(SessionEnvironment(honeypot_root=str(tmp_path)))
    assert commands.handle('head', ['-n', '1', '/note'])[1] == b'a\n'
    assert commands.handle('tail', ['-n', '0', '/note'])[1] == b''
    assert commands.handle('tail', ['-n', '2', '/note'])[1] == b'b\nc\n'
    for command in ('head', 'tail', 'grep'):
        args = ['x', '/missing'] if command == 'grep' else ['/missing']
        code, _, error = commands.handle(command, args)
        assert code != 0 and b'No such file' in error
    (tmp_path / 'big').write_bytes(b'x' * 1048576)
    assert commands.handle('cat', ['/big', '/big'])[0] != 0


def test_redis_memory_pressure_preserves_existing_content(isolated_redis):
    client = ScopedRedis(isolated_redis, 'session:pressure:')
    hv = hypervisor(client)
    hv.initialize_filesystem()
    inode = hv.create_file(hv._resolve_path_sync('/tmp'), 'data')
    mutate_content(client, inode, buf=b'original')
    digest = client.hget(f'fs:inode:{inode}', 'content_hash')
    isolated_redis.config_set('maxmemory', 1)
    try:
        with pytest.raises(redis.RedisError):
            mutate_content(client, inode, buf=b'new')
        assert client.hget(f'fs:inode:{inode}', 'content_hash') == digest
        assert read_blob(client, digest) == b'original'
    finally:
        isolated_redis.config_set('maxmemory', 0)


def test_expired_generation_lease_recovers(isolated_redis):
    client = ScopedRedis(isolated_redis, 'session:lease:')
    hv = hypervisor(client)
    hv.initialize_filesystem()
    inode = hv._resolve_path_sync('/etc/passwd')
    isolated_redis.psetex(client.key(f'fs:generating:{inode}'), 50, 'dead-worker')
    generator = GenerationOrchestrator(client, UbuntuProfile())
    try:
        assert b'ubuntu:x:1000:' in generator.get_or_generate(inode, '/etc/passwd', 'test', {})
    finally:
        generator.close()


@pytest.mark.parametrize('response', [b'[]', b'{', b'{"response":null}', b'x' * 262145])
def test_malformed_http_model_results(monkeypatch, response):
    reply = Mock()
    reply.iter_content.return_value = [response]
    monkeypatch.setattr('chronos.intelligence.inference.requests.post', Mock(return_value=reply))
    runtime = InferenceRuntime()
    with pytest.raises(ModelUnreachableError):
        runtime.generate('trusted prompt')
    reply.close.assert_called_once()
    assert runtime.circuit_breaker.models['llama3:8b'].failures == 1


def test_streamed_model_completion(monkeypatch):
    reply = Mock()
    reply.iter_content.return_value = [b'{"response":"hel', b'lo", "done":false}\n',
                                       b'{"response":" world", "done":true}\n']
    post = Mock(return_value=reply)
    monkeypatch.setattr('chronos.intelligence.inference.requests.post', post)
    assert InferenceRuntime().generate('trusted prompt') == 'hello world'
    assert post.call_args.kwargs['json']['stream'] is True
    reply.close.assert_called_once()


def test_nginx_rejects_invented_backend_and_missing_include():
    from chronos.intelligence.artifact_policy import ArtifactPolicyEngine
    from chronos.intelligence.ubuntu_profile import UbuntuProfile
    from chronos.intelligence.validator import SemanticValidator
    from chronos.intelligence.fallback import FallbackProvider
    path = '/etc/nginx/nginx.conf'
    machine = {**UbuntuProfile().build_machine_state(), 'artifact_path': path}
    policy = ArtifactPolicyEngine().resolve('nginx.conf', path, machine)
    validator = SemanticValidator()
    assert not validator.validate('http { upstream backend { server web01:8080; } }', policy, machine).accepted
    assert not validator.validate('include /missing.conf; root /var/www/html;', policy, machine).accepted
    fallback = FallbackProvider().get_degraded_content('nginx.conf', policy, path, machine)
    assert validator.validate(fallback.decode(), policy, machine).accepted


@pytest.mark.parametrize('body', [b'{"response":"partial", "done":false}\n',
                                b'{"response":"partial", "done":true,"done_reason":"length"}\n'])
def test_incomplete_stream_not_committed(monkeypatch, body):
    reply = Mock()
    reply.iter_content.return_value = [body]
    monkeypatch.setattr('chronos.intelligence.inference.requests.post', Mock(return_value=reply))
    with pytest.raises(ModelUnreachableError):
        InferenceRuntime().generate('trusted prompt')
