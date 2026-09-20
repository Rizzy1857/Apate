"""Opt-in actual manifest generation; local Ollama and disposable Redis only.

Run with CHRONOS_LIVE_FILES=1 PYTHONPATH=src python3 -m pytest
tests/integration/verify_live_files.py -s. No runtime or validator is mocked.
"""
import json
import os
import random
import time
import uuid

import pytest
import requests
import logging

from chronos.core.database import Database
from chronos.core.scoped_redis import ScopedRedis
from chronos.core.state import StateHypervisor
from chronos.intelligence.inference import InferenceRuntime
from chronos.intelligence.orchestrator import GenerationOrchestrator
from chronos.intelligence.ubuntu_profile import UbuntuProfile


@pytest.mark.skipif(os.environ.get('CHRONOS_LIVE_FILES') != '1', reason='Explicit local-model opt-in required')
def test_real_manifest_files(isolated_redis, tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    profile = UbuntuProfile()
    session = str(uuid.uuid4())
    scoped = ScopedRedis(isolated_redis, f'session:{session}:')
    database = Database.__new__(Database)
    database.client = scoped
    database._load_scripts()
    state = StateHypervisor.__new__(StateHypervisor)
    state.db, state.redis = database, scoped
    state.initialize_filesystem()
    runtime = InferenceRuntime()
    generator = GenerationOrchestrator(scoped, profile, runtime=runtime, max_workers=1)
    rows = []
    old_random = random.getstate()
    random.seed(0)
    try:
        available = requests.get(f'http://{runtime.host}:11434/api/tags', timeout=5).json()
        installed = {model['name'] for model in available['models']}
        required = set(generator.policy_engine._model_routing.values())
        assert required <= installed, f'Missing configured models: {sorted(required-installed)}'
        manifest = json.loads(profile.build_machine_state()['filesystem_manifest'])
        reports = []
        for trial in range(2):
            print(f"\n=== Trial {trial+1} ===")
            isolated_redis.flushdb()
            state.initialize_filesystem()
            generator._futures.clear()
            
            rows = []
            for entry in manifest['entries']:
                if entry['class'] != 'ai_backed':
                    continue
                path = entry['path']
                print(f"Testing {path}...")
                inode = state._resolve_path_sync(path)
                started = time.monotonic()
                data = generator.get_or_generate(inode, path, session, {})
                pending_reads = 0
                deadline = started + 65
                while data is None and time.monotonic() < deadline:
                    pending_reads += 1
                    time.sleep(.1)
                    data = generator.get_or_generate(inode, path, session, {})
                assert isinstance(data, bytes), f'Generation did not settle: {path}'
                cold_seconds = time.monotonic() - started
                started = time.monotonic()
                assert generator.get_or_generate(inode, path, session, {}) == data
                cached_seconds = time.monotonic() - started
                metadata = scoped.hgetall(f'fs:inode:{inode}')
                provenance = scoped.hgetall(f"fs:blob_meta:{metadata['content_hash']}")
                assert len(data) <= 65536 and b'\0' not in data
                (tmp_path / f"trial_{trial}_{path.strip('/').replace('/', '__')}").write_bytes(data)
                rows.append({'path': path, 'bytes': len(data), 'first_read_seconds': cold_seconds,
                             'cached_read_seconds': cached_seconds, 'pending_reads': pending_reads,
                             'source': provenance.get('generation_source'), 'model': provenance.get('model'),
                             'validated': provenance.get('validated')})
            
            report = {'trial': trial, 'files': rows}
            reports.append(report)
            print(json.dumps(report, indent=2))
            
            failures = [r['path'] for r in rows if r['source'] != 'llm']
            assert not failures, f"Trial {trial+1} failed LLM generation for: {failures}"
            
        (tmp_path / 'evaluation.json').write_text(json.dumps({'models': available['models'], 'trials': reports, 'artifacts': str(tmp_path)}, indent=2))
    finally:
        generator.close()
        random.setstate(old_random)
