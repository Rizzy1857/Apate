"""Host-side disposable load-test orchestration; no operator services touched."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

root = Path(__file__).resolve().parents[2]
prefix = 'apate-load-' + uuid.uuid4().hex[:10]
image = prefix + ':test'
names = {key: prefix + '-' + key for key in ('net', 'redis', 'pg', 'core', 'clients')}


def docker(*args, check=True):
    result = subprocess.run(['docker', *args], text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    if args and args[0] == 'logs':
        return result.stdout + result.stderr
    return result.stdout.strip()


def main():
    process = None
    samples = []
    pg_paused = False
    fault_started = None
    fault_recovered = False
    fault = os.environ.get('APATE_LOAD_FAULT', '')
    if fault not in ('', 'postgres', 'redis', 'core'):
        raise ValueError('APATE_LOAD_FAULT must be empty, postgres, redis or core')
    try:
        docker('build', '-q', '-t', image, str(root))
        docker('network', 'create', '--internal', names['net'])
        docker('run', '-d', '--name', names['redis'], '--network', names['net'],
               'redis:7-alpine', 'redis-server', '--appendonly', 'yes', '--maxmemory', '256mb', '--maxmemory-policy', 'noeviction')
        docker('run', '-d', '--name', names['pg'], '--network', names['net'],
               '-e', 'POSTGRES_USER=chronos', '-e', 'POSTGRES_PASSWORD=chronos_dev_password',
               '-e', 'POSTGRES_DB=chronos', 'postgres:15-alpine')
        for _ in range(60):
            ready = docker('exec', names['pg'], 'pg_isready', '-U', 'chronos', check=False)
            if 'accepting connections' in ready:
                break
            time.sleep(1)
        else:
            raise AssertionError('Disposable PostgreSQL did not become ready')
        diagnostic_command = (['python3', '-c',
            'import faulthandler; faulthandler.dump_traceback_later(100, repeat=False); from chronos.core.main import main; main()']
            if os.environ.get('APATE_LOAD_STACKS') == '1' else [])
        docker('run', '-d', '--name', names['core'], '--network', names['net'],
               '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
               '--tmpfs', '/mnt/honeypot:rw,nosuid,size=1m', '-v', '/var/lib/chronos',
               '--cap-drop', 'ALL', '--cap-add', 'SYS_ADMIN', '--cap-add', 'SYS_CHROOT',
               '--cap-add', 'SETUID', '--cap-add', 'SETGID', '--cap-add', 'KILL',
               '--device', '/dev/fuse', '--security-opt', 'apparmor=unconfined',
               '--security-opt', 'no-new-privileges:true', '--pids-limit', '192',
               '--memory', '2g', '--cpus', '2', '-e', 'REDIS_HOST=' + names['redis'],
               '-e', 'POSTGRES_HOST=' + names['pg'], image, *diagnostic_command)
        for _ in range(60):
            mounted = docker('exec', names['core'], 'python3', '-c',
                             'from chronos.gateway.containment import is_honeypot_mount; print(is_honeypot_mount("/mnt/honeypot"))', check=False)
            if mounted == 'True':
                break
            time.sleep(1)
        else:
            raise AssertionError('Disposable core did not mount FUSE')
        process = subprocess.Popen(['docker', 'run', '--rm', '--name', names['clients'],
            '--network', names['net'], '-e', 'APATE_CORE_HOST=' + names['core'],
            '-e', 'REDIS_HOST=' + names['redis'], '-e', 'POSTGRES_HOST=' + names['pg'],
            '-e', 'APATE_LOAD_SECONDS=' + os.environ.get('APATE_LOAD_SECONDS', '120'),
            '-e', 'APATE_LOAD_FAULT=' + fault,
            '-v', str(root / 'tests') + ':/app/tests:ro', image,
            'python3', 'tests/integration/' + ('verify_restart.py' if fault in ('redis', 'core') else 'verify_load.py')], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)
        print(json.dumps({'started': names, 'duration': os.environ.get('APATE_LOAD_SECONDS', '120')}), flush=True)
        while process.poll() is None:
            if fault and fault_started is None:
                count = docker('exec', names['pg'], 'psql', '-U', 'chronos', '-Atc',
                               "SELECT count(*) FROM audit_log WHERE operation='ssh_command'", check=False)
                if count.isdigit() and int(count) >= 64:
                    if fault == 'postgres':
                        docker('pause', names['pg'])
                        pg_paused = True
                    elif fault == 'redis':
                        docker('stop', '-t', '1', names['redis'])
                    else:
                        docker('kill', '--signal', 'KILL', names['core'])
                    fault_started = time.monotonic()
                    print(json.dumps({'fault': fault + '_interrupted', 'audited_before': int(count)}), flush=True)
            if fault in ('redis', 'core') and fault_started is not None and not fault_recovered and time.monotonic() - fault_started >= 30:
                docker('start', names[fault])
                for _ in range(60):
                    if docker('exec', names['redis'], 'redis-cli', 'ping', check=False) == 'PONG':
                        break
                    time.sleep(1)
                else:
                    raise AssertionError('Redis did not recover')
                docker('exec', names['redis'], 'redis-cli', 'set', 'test:fault_recovered', '1')
                fault_recovered = True
                print(json.dumps({'fault': fault + '_restarted'}), flush=True)
            if pg_paused and time.monotonic() - fault_started >= 30:
                docker('unpause', names['pg'])
                pg_paused = False
                fault_recovered = True
                print(json.dumps({'fault': 'postgres_resumed', 'outage_seconds': time.monotonic() - fault_started}), flush=True)
            sample = docker('stats', '--no-stream', '--format', '{{json .}}', names['core'], check=False)
            if sample:
                samples.append(json.loads(sample))
                print(sample, flush=True)
            time.sleep(5)
        output = process.communicate()[0]
        print(output, flush=True)
        assert process.returncode == 0, 'Load client failed'
        if fault:
            assert fault_recovered, 'Fault was not injected and recovered during the load test'
        state = json.loads(docker('inspect', '--format', '{{json .State}}', names['core']))
        assert state['Running'] and not state['OOMKilled'], state
        print(json.dumps({'runtime_state': state, 'samples': len(samples), 'result': 'PASS'}), flush=True)
    finally:
        if pg_paused:
            docker('unpause', names['pg'], check=False)
        if process is not None and process.poll() not in (0, None):
            print(docker('inspect', '--format', '{{json .State}}', names['core'], check=False), flush=True)
            logs = docker('logs', names['core'], check=False)
            diagnostic = root / '.pytest_cache' / (prefix + '-core.log')
            diagnostic.parent.mkdir(parents=True, exist_ok=True)
            diagnostic.write_text(logs)
            print(json.dumps({'failure_log': str(diagnostic)}), flush=True)
            lines = logs.splitlines()
            excerpts = 0
            for index, line in enumerate(lines):
                if any(word in line.lower() for word in ('error', 'exception', 'traceback', 'timeout')):
                    print('\n'.join(lines[max(0, index-1):index+8]), flush=True)
                    excerpts += 1
                    if excerpts >= 10:
                        break  # Full diagnostics remain in the retained file.
        docker('rm', '-fv', names['clients'], names['core'], names['redis'], names['pg'], check=False)
        docker('network', 'rm', names['net'], check=False)


if __name__ == '__main__':
    main()
