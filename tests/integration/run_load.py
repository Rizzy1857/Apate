"""Host-side disposable load-test orchestration; no operator services touched."""
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time
import uuid
import hashlib
from datetime import datetime, timezone
from freeze_release_candidate import image_inventory
from load_state import verify_image_sources

root = Path(__file__).resolve().parents[2]
prefix = 'apate-load-' + uuid.uuid4().hex[:10]
image = os.environ.get('APATE_LOAD_IMAGE', prefix + ':test')
owns_image = 'APATE_LOAD_IMAGE' not in os.environ
names = {key: prefix + '-' + key for key in ('net', 'redis', 'pg', 'core', 'clients')}
REDIS_IMAGE = 'redis:7-alpine@sha256:02f2cc4882f8bf87c79a220ac958f58c700bdec0dfb9b9ea61b62fb0e8f1bfcf'
POSTGRES_IMAGE = 'postgres:15-alpine@sha256:1d1095b0503145be79c79239372aefadfacf6b7c33c9245bbf99ce4b6b89c737'


def bytes_value(value):
    """Parse the usage half of Docker's human-readable memory field."""
    match = re.fullmatch(r'\s*([0-9.]+)\s*([KMGT]?i?B)\s*', value)
    if not match:
        raise ValueError(f'Unrecognized Docker size: {value!r}')
    scales = {
        'B': 1, 'KB': 1000, 'MB': 1000 ** 2, 'GB': 1000 ** 3,
        'KiB': 1024, 'MiB': 1024 ** 2, 'GiB': 1024 ** 3,
        'TiB': 1024 ** 4,
    }
    return float(match.group(1)) * scales[match.group(2)]


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
    persistent = os.environ.get('APATE_LOAD_PERSISTENT_RUNS', '0')
    if persistent not in ('0', '1'):
        raise ValueError('APATE_LOAD_PERSISTENT_RUNS must be 0 or 1')
    authenticated = os.environ.get('APATE_LOAD_REDIS_AUTH', '0')
    if authenticated not in ('0', '1'):
        raise ValueError('APATE_LOAD_REDIS_AUTH must be 0 or 1')
    redis_password = uuid.uuid4().hex if authenticated == '1' else ''
    output_dir = Path(os.environ.get('APATE_LOAD_OUTPUT', str(root / '.pytest_cache' / prefix)))
    output_dir.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (output_dir / name).write_text(json.dumps(value, indent=2) + '\n')
    started_at = datetime.now(timezone.utc).isoformat()
    source_files = sorted(p for folder in ('src', 'config', 'tests/integration')
                          for p in (root / folder).rglob('*')
                          if p.is_file() and not {'target', '__pycache__'}.intersection(p.parts))
    source_hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in source_files}
    save('source_hashes.json', source_hashes)
    if fault not in ('', 'postgres', 'redis', 'core'):
        raise ValueError('APATE_LOAD_FAULT must be empty, postgres, redis or core')
    try:
        if owns_image:
            docker('build', '-q', '-t', image, str(root))
        inventory = image_inventory(image)
        match = verify_image_sources(source_hashes, inventory['application_files'])
        save('image_inventory.json', inventory)
        save('image_source_match.json', match)
        save('run.json', {'started_at': started_at, 'names': names,
                         'image_id': docker('image', 'inspect', '--format', '{{.Id}}', image),
                         'parameters': {key: value for key, value in os.environ.items()
                                        if key.startswith('APATE_LOAD_')}})
        docker('network', 'create', '--internal', names['net'])
        redis_command = ['redis-server', '--appendonly', 'yes', '--maxmemory', '256mb',
                         '--maxmemory-policy', 'noeviction']
        if redis_password:
            redis_command += ['--requirepass', redis_password]
        docker('run', '-d', '--name', names['redis'], '--network', names['net'],
               '-e', 'REDISCLI_AUTH=' + redis_password,
               os.environ.get('APATE_LOAD_REDIS_IMAGE', REDIS_IMAGE), *redis_command)
        docker('run', '-d', '--name', names['pg'], '--network', names['net'],
               '-e', 'POSTGRES_USER=chronos', '-e', 'POSTGRES_PASSWORD=chronos_dev_password',
               '-e', 'POSTGRES_DB=chronos',
               os.environ.get('APATE_LOAD_POSTGRES_IMAGE', POSTGRES_IMAGE))
        for _ in range(60):
            ready = docker('exec', names['pg'], 'pg_isready', '-U', 'chronos', check=False)
            if 'accepting connections' in ready:
                break
            time.sleep(1)
        else:
            raise AssertionError('Disposable PostgreSQL did not become ready')
        if redis_password:
            rejected = docker('exec', '-e', 'REDISCLI_AUTH=', names['redis'],
                              'redis-cli', 'ping', check=False)
            assert 'NOAUTH' in rejected, 'Test Redis unexpectedly permits unauthenticated commands'
            assert docker('exec', names['redis'], 'redis-cli', 'ping') == 'PONG'
            save('redis_auth_verification.json', {'unauthenticated_ping': 'rejected',
                                                 'authenticated_ping': 'accepted'})
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
               '-e', 'APATE_SESSION_ORIGIN=scripted_test',
               '-e', 'CHRONOS_PERSISTENT_RUNS=' + persistent,
               '-e', 'REDIS_PASSWORD=' + redis_password,
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
            '-e', 'APATE_LOAD_CLIENTS=' + os.environ.get('APATE_LOAD_CLIENTS', '32'),
            '-e', 'APATE_LOAD_MAX_COMMANDS=' + os.environ.get('APATE_LOAD_MAX_COMMANDS', '900'),
            '-e', 'APATE_LOAD_INTERVAL=' + os.environ.get('APATE_LOAD_INTERVAL', '0.2'),
            '-e', 'APATE_LOAD_ROTATE_SECONDS=' + os.environ.get('APATE_LOAD_ROTATE_SECONDS', '3300'),
            '-e', 'APATE_LOAD_FAULT=' + fault,
            '-e', 'APATE_LOAD_PERSISTENT_RUNS=' + persistent,
            '-e', 'REDIS_PASSWORD=' + redis_password,
            '-v', str(root / 'tests') + ':/app/tests:ro', image,
            'python3', 'tests/integration/' + ('verify_restart.py' if fault in ('redis', 'core') else 'verify_load.py')], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)
        print(json.dumps({
            'started': names,
            'duration': os.environ.get('APATE_LOAD_SECONDS', '120'),
            'clients': os.environ.get('APATE_LOAD_CLIENTS', '32'),
            'max_commands_per_client': os.environ.get('APATE_LOAD_MAX_COMMANDS', '900'),
            'command_interval_seconds': os.environ.get('APATE_LOAD_INTERVAL', '0.2'),
        }), flush=True)
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
                with (output_dir / 'samples.jsonl').open('a') as stream:
                    stream.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(),
                                             **samples[-1]}) + '\n')
                print(sample, flush=True)
            time.sleep(5)
        output = process.communicate()[0]
        (output_dir / 'client.log').write_text(output)
        print(output, flush=True)
        assert process.returncode == 0, 'Load client failed'
        if fault:
            assert fault_recovered, 'Fault was not injected and recovered during the load test'
        state = json.loads(docker('inspect', '--format', '{{json .State}}', names['core']))
        assert state['Running'] and not state['OOMKilled'], state
        memory = [bytes_value(sample['MemUsage'].split('/')[0]) for sample in samples]
        pids = [int(sample['PIDs']) for sample in samples]
        window = min(12, len(memory))
        memory_start = statistics.median(memory[:window])
        memory_end = statistics.median(memory[-window:])
        # Freeze the soak interpretation before the run: tolerate allocator/cache
        # settling, but not more than 128 MiB median growth across the observation.
        allowed_growth = 128 * 1024 * 1024
        assert memory_end <= memory_start + allowed_growth, {
            'memory_start': memory_start, 'memory_end': memory_end,
            'allowed_growth': allowed_growth,
        }
        resource_summary = {
            'samples': len(samples),
            'memory_start_median_bytes': memory_start,
            'memory_end_median_bytes': memory_end,
            'memory_max_bytes': max(memory),
            'pids_start_median': statistics.median(pids[:window]),
            'pids_end_median': statistics.median(pids[-window:]),
            'pids_max': max(pids),
            'allowed_memory_growth_bytes': allowed_growth,
        }
        print(json.dumps({'runtime_state': state, 'resources': resource_summary,
                          'result': 'PASS'}), flush=True)
        save('result.json', {'result': 'PASS', 'runtime_state': state,
                             'resources': resource_summary, 'started_at': started_at,
                             'finished_at': datetime.now(timezone.utc).isoformat()})
    except BaseException as exc:
        save('result.json', {'result': 'FAIL', 'error': repr(exc), 'started_at': started_at,
                             'finished_at': datetime.now(timezone.utc).isoformat()})
        raise
    finally:
        (output_dir / 'core.log').write_text(docker('logs', names['core'], check=False))
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
        if owns_image:
            docker('image', 'rm', image, check=False)


if __name__ == '__main__':
    main()
