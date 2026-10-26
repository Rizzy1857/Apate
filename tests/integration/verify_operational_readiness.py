"""Cold backup/restore and real bounded storage faults on disposable resources.

Never accepts an existing project or volume. Backups contain private synthetic
state and credentials; the new output directory is mode 0700 and gitignored.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


SEED = r'''
import json, os, time, hashlib
import paramiko, psycopg2, redis
r = redis.Redis(host='redis-store', password=os.environ['REDIS_PASSWORD'], decode_responses=True)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # disposable container loopback
c.connect('127.0.0.1', port=2222, username='ubuntu', password='synthetic', look_for_keys=False, allow_agent=False)
ch = c.invoke_shell(); ch.settimeout(15)
def prompt():
    out = b''
    while not out.endswith(b'$ '):
        part = ch.recv(65536)
        assert part and len(out) < 262144
        out += part
    return out.decode()
prompt()
token = os.environ['PROBE_TOKEN']
ch.sendall(('echo ' + token + ' > /tmp/recovery-marker; cd /tmp; pwd\n').encode())
assert '/tmp\r\n' in prompt()
c.close()
deadline = time.monotonic() + 60
while True:
    runs = list(r.scan_iter('chronos:run:*'))
    if len(runs) == 1 and r.hget(runs[0], 'status') == 'paused': break
    assert time.monotonic() < deadline, 'Run did not pause'
    time.sleep(1)
run = r.hgetall(runs[0])
conn = psycopg2.connect(host='db-store', user='chronos', password=os.environ['POSTGRES_PASSWORD'], dbname='chronos')
deadline = time.monotonic() + 60
while True:
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM session_evidence WHERE session_id=%s', (run['session_id'],))
        if cur.fetchone()[0] == 1: break
    assert time.monotonic() < deadline, 'Evidence did not finalize'
    time.sleep(1)
with conn.cursor() as cur:
    cur.execute('SELECT event_id::text FROM audit_log ORDER BY id')
    events = [row[0] for row in cur.fetchall()]
assert events
print(json.dumps({'run_id': run['run_id'], 'session_id': run['session_id'],
 'persona': run['persona'], 'events': events,
 'host_key_sha256': hashlib.sha256(open('/var/lib/chronos/ssh_host_rsa_key','rb').read()).hexdigest()}))
'''

VERIFY = r'''
import json, os, hashlib, time
import paramiko, psycopg2, redis
from chronos.core.research_runs import arm_resume
from chronos.watcher.export_report import load_session, write_bundle, _metadata_from_environment
from argparse import Namespace
from pathlib import Path
base = json.loads(os.environ['PROBE_BASELINE'])
r = redis.Redis(host='redis-store', password=os.environ['REDIS_PASSWORD'], decode_responses=True)
assert r.hget('chronos:run:' + base['run_id'], 'persona') == base['persona']
assert hashlib.sha256(open('/var/lib/chronos/ssh_host_rsa_key','rb').read()).hexdigest() == base['host_key_sha256']
conn = psycopg2.connect(host='db-store', user='chronos', password=os.environ['POSTGRES_PASSWORD'], dbname='chronos')
deadline = time.monotonic() + 60
while True:
    with conn.cursor() as cur:
        cur.execute('SELECT event_id::text FROM audit_log')
        ids = [row[0] for row in cur.fetchall()]
    if os.environ['PROBE_PENDING'] in ids: break
    assert time.monotonic() < deadline, 'Restored outbox not delivered'
    time.sleep(1)
assert set(base['events']) <= set(ids)
assert ids.count(os.environ['PROBE_PENDING']) == 1
arm_resume(r, base['run_id'])
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('127.0.0.1', port=2222, username='ubuntu', password='synthetic', look_for_keys=False, allow_agent=False)
ch = c.invoke_shell(); ch.settimeout(15)
def prompt():
    out = b''
    while not out.endswith(b'$ '):
        part = ch.recv(65536)
        assert part and len(out) < 262144
        out += part
    return out.decode()
assert '/tmp' in prompt()
ch.sendall(b'pwd; cat /tmp/recovery-marker\n')
response = prompt()
assert '/tmp\r\n' in response and os.environ['PROBE_TOKEN'] + '\r\n' in response, response
c.close()
conn.rollback()  # End verification reads before opening the export snapshot.
events, snapshot = load_session(conn, base['session_id'])
conn.close()
meta = _metadata_from_environment(Namespace(run_id=None, session_id=base['session_id']), snapshot, events)
for mode in ('raw', 'redacted'):
    output = Path('/tmp/restored-export-' + mode)
    write_bundle(output, events, meta, mode=mode)
    assert (output/'complete.json').is_file()
    complete = json.loads((output/'complete.json').read_text())
    for name, digest in complete['sha256'].items():
        assert hashlib.sha256((output/name).read_bytes()).hexdigest() == digest
    report = json.loads((output/'report.json').read_text())
    assert report['commands']
print(json.dumps({'restored_persona': True, 'restored_cwd_and_marker': True,
 'restored_host_key': True, 'original_audit_ids_retained': len(base['events']),
 'pending_outbox_delivered_once': True, 'raw_and_redacted_exports': True}))
'''

DISK = r'''
import errno, os, sqlite3
from chronos.core.audit_spool import AuditSpool
spool = AuditSpool('/pressure/audit.sqlite3')
spool.append(['acknowledged-before-pressure'])
spool.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
with open('/pressure/filler','wb',buffering=0) as f:
    try:
        while True: f.write(b'x'*4096); f.flush()
    except OSError as e:
        assert e.errno == errno.ENOSPC
try:
    spool.append(['must-not-acknowledge-' + 'x'*60000])
except (sqlite3.Error, OSError): pass
else: raise AssertionError('Full filesystem admitted event')
os.unlink('/pressure/filler')
spool.close()
spool = AuditSpool('/pressure/audit.sqlite3')
assert spool.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert [p for _,p in spool.pending()] == [['acknowledged-before-pressure']]
spool.append(['recovered'])
assert spool.count() == 2
spool.close()
print('PASS: actual ENOSPC rejects append, retains prior event and recovers')
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', required=True)
    p.add_argument('--redis', required=True)
    p.add_argument('--postgres', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(args.output, 0o700)
    root = Path(__file__).resolve().parents[2]
    prefix = 'mirage-ops-' + uuid.uuid4().hex[:10]
    projects = [prefix + '-source', prefix + '-restore']
    pressure = prefix + '-pressure'
    env = {**os.environ, 'MIRAGE_IMAGE': args.core, 'MIRAGE_REDIS_IMAGE': args.redis,
           'MIRAGE_POSTGRES_IMAGE': args.postgres, 'REDIS_PASSWORD': uuid.uuid4().hex,
           'POSTGRES_PASSWORD': uuid.uuid4().hex, 'PROBE_TOKEN': uuid.uuid4().hex,
           'PROBE_PENDING': str(uuid.uuid4())}
    def run(cmd, timeout=180, **kw):
        return subprocess.run(cmd, env=env, check=True, capture_output=True,
                              text=True, timeout=timeout, **kw).stdout.strip()
    def compose(project, *cmd):
        return run(['docker','compose','-p',project,'-f',str(root/'compose.azure-staging.yml'),*cmd])
    def probe(project, code, **variables):
        switches = []
        for key, value in variables.items(): switches += ['-e', key + '=' + value]
        return compose(project, 'exec','-T', *switches, 'core-engine','python3','-c',code)
    def ready(project):
        compose(project, 'up','-d','--pull','never')
        deadline = time.monotonic() + 90
        while True:
            try:
                probe(project, "import socket; socket.create_connection(('127.0.0.1',2222),2).close()")
                return
            except subprocess.CalledProcessError:
                if time.monotonic() >= deadline: raise
                time.sleep(1)
    outcome = {'result':'FAIL','projects':projects}
    try:
        ready(projects[0])
        baseline = json.loads(probe(projects[0], SEED, PROBE_TOKEN=env['PROBE_TOKEN']))
        compose(projects[0], 'stop','core-engine')
        # A pending durable event models evidence not yet projected to PostgreSQL.
        inject = "from chronos.core.audit_spool import AuditSpool; import datetime; s=AuditSpool('/var/lib/chronos/audit.sqlite3'); s.append((" + repr(baseline['session_id']) + ",datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup_probe','',0,{'origin':'synthetic'}),event_id=" + repr(env['PROBE_PENDING']) + "); s.close()"
        run(['docker','run','--rm','--network','none','-v',projects[0]+'_audit-spool:/var/lib/chronos',args.core,'python3','-c',inject])
        compose(projects[0], 'stop')  # all three writers stopped before any snapshot
        images = {}
        for service in ('core-engine','redis-store','db-store'):
            cid = compose(projects[0], 'ps','-a','-q',service)
            images[service] = run(['docker','inspect','--format','{{.Image}}',cid])
        manifest = {'images':images,'volumes':{},'baseline':baseline}
        secret_file = args.output/'credentials.json'
        with open(secret_file, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
            json.dump({k:env[k] for k in ('REDIS_PASSWORD','POSTGRES_PASSWORD')},f)
        for volume in ('redis-data','postgres-data','audit-spool'):
            archive = args.output/(volume+'.tar')
            with open(archive, 'xb', opener=lambda path, flags: os.open(path,flags,0o600)) as f:
                subprocess.run(['docker','run','--rm','--network','none','-v',projects[0]+'_'+volume+':/volume:ro',args.core,'tar','-cpf','-','-C','/volume','.'],stdout=f,stderr=subprocess.PIPE,check=True,timeout=120)
            with archive.open('rb') as f:
                digest = hashlib.file_digest(f,'sha256').hexdigest()
            manifest['volumes'][volume] = {'bytes':archive.stat().st_size, 'sha256':digest}
        (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        compose(projects[0], 'down')  # keep original volumes until verification finishes
        compose(projects[1], 'create','--pull','never')
        # Physical volume copies require exactly matching image/platform/DB major.
        for volume, details in manifest['volumes'].items():
            archive = args.output/(volume+'.tar')
            with archive.open('rb') as f:
                assert hashlib.file_digest(f,'sha256').hexdigest() == details['sha256']
            with archive.open('rb') as f:
                subprocess.run(['docker','run','--rm','-i','--network','none','-v',projects[1]+'_'+volume+':/volume',args.core,'tar','-xpf','-','-C','/volume'],stdin=f,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=120)
        ready(projects[1])
        outcome.update(json.loads(probe(projects[1],VERIFY,PROBE_BASELINE=json.dumps(baseline),PROBE_TOKEN=env['PROBE_TOKEN'],PROBE_PENDING=env['PROBE_PENDING'])))
        # Docker cp cannot reliably read tmpfs here; archive through exec.
        for mode in ('raw','redacted'):
            with open(args.output/('export-'+mode+'.tar'), 'xb', opener=lambda path, flags: os.open(path,flags,0o600)) as f:
                subprocess.run(['docker','compose','-p',projects[1],'-f',str(root/'compose.azure-staging.yml'),
                    'exec','-T','core-engine','tar','-cpf','-','-C','/tmp','restored-export-'+mode],
                    env=env,stdout=f,stderr=subprocess.PIPE,check=True,timeout=60)
        outcome['disk_full'] = run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/pressure:rw,size=4m','-e','PYTHONDONTWRITEBYTECODE=1',args.core,'python3','-c',DISK])
        run(['docker','run','-d','--name',pressure,'--network','none','-e','REDISCLI_AUTH='+env['REDIS_PASSWORD'],args.redis,'redis-server','--save','','--maxmemory','8mb','--maxmemory-policy','noeviction','--requirepass',env['REDIS_PASSWORD']])
        for _ in range(30):
            try:
                assert run(['docker','exec',pressure,'redis-cli','ping']) == 'PONG'
                break
            except (subprocess.CalledProcessError,AssertionError): time.sleep(1)
        assert run(['docker','exec',pressure,'redis-cli','set','retained','acknowledged']) == 'OK'
        rejected = False
        for number in range(16):
            reply = run(['docker','exec','-i',pressure,'redis-cli','-x','set','pressure:'+str(number)],input='x'*1024*1024)
            if 'OOM' in reply:
                rejected = True
                break
        assert rejected, 'Redis did not reach configured storage limit'
        assert run(['docker','exec',pressure,'redis-cli','get','retained']) == 'acknowledged'
        for number in range(16): run(['docker','exec',pressure,'redis-cli','del','pressure:'+str(number)])
        assert run(['docker','exec',pressure,'redis-cli','set','after','recovered']) == 'OK'
        outcome.update(result='PASS',redis_noeviction_oom_recovery=True)
    except BaseException as e:
        if isinstance(e, subprocess.CalledProcessError):
            outcome['error'] = 'Docker verification subprocess exited ' + str(e.returncode)
            outcome['stderr'] = str(e.stderr)[-6000:]
            raise RuntimeError(outcome['error'] + ': ' + outcome['stderr']) from None
        outcome['error'] = repr(e)
        raise
    finally:
        failures = []
        for project in projects:
            try:
                (args.output/(project+'.log')).write_text(compose(project,'logs','--no-color','core-engine'))
            except Exception as e: failures.append('logs: ' + str(e))
            try:
                compose(project,'down','--volumes','--remove-orphans')
            except Exception as e: failures.append(str(e))
        subprocess.run(['docker','rm','-f',pressure],capture_output=True,timeout=30)
        outcome['cleanup_succeeded'] = not failures
        if failures: outcome.update(result='FAIL',cleanup_errors=failures)
        (args.output/'result.json').write_text(json.dumps(outcome,indent=2)+'\n')
        print(json.dumps(outcome,indent=2))
        if failures: raise RuntimeError('Disposable cleanup incomplete')


if __name__ == '__main__':
    main()
