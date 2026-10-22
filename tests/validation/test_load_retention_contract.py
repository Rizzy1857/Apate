import json
from pathlib import Path
import runpy

import pytest


helpers = runpy.run_path(str(Path(__file__).parents[1] / 'integration' / 'load_state.py'))


def test_image_identity_requires_matching_application_not_only_a_tag():
    source = {'src/chronos/core/main.py': 'current', 'config/ubuntu.yaml': 'profile',
              'src/chronos/dashboard/src/main.rs': 'separate',
              'tests/integration/run_load.py': 'harness'}
    image = {'src/chronos/core/main.py': 'current', 'config/ubuntu.yaml': 'profile'}
    assert helpers['verify_image_sources'](source, image)['application_files'] == 2
    for invalid in ({**image, 'src/chronos/core/main.py': 'stale'},
                    {'config/ubuntu.yaml': 'profile'},
                    {**image, 'src/unexpected.py': 'extra'}):
        with pytest.raises(ValueError, match='does not match'):
            helpers['verify_image_sources'](source, invalid)


def test_load_contract_requires_pause_retention_and_removed_ownership(isolated_redis):
    client = isolated_redis
    client.hset('chronos:run:synthetic', mapping={
        'run_id': 'synthetic', 'status': 'active', 'device_id': 'device',
        'persona': json.dumps({'device_id': 'device'}),
    })
    client.set('run:synthetic:fs:next_inode', '10')
    with pytest.raises(AssertionError):
        helpers['retained_runs'](client, 1)
    client.hset('chronos:run:synthetic', 'status', 'paused')
    client.set('session:synthetic:run_id', 'synthetic')
    assert helpers['cleanup_pending'](client)
    with pytest.raises(AssertionError, match='ownership'):
        helpers['retained_runs'](client, 1)
    client.delete('session:synthetic:run_id')
    assert helpers['retained_runs'](client, 1)['paused_runs'] == 1
    client.delete('run:synthetic:fs:next_inode')
    with pytest.raises(AssertionError, match='filesystem'):
        helpers['retained_runs'](client, 1)
