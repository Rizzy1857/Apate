"""Check Git's actual ignore behavior, including paths not created on disk."""
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize('path,ignored', [
    ('.env', True), ('.env.azure', True), ('.env.test.local', True),
    ('.env.example', False), ('config/.env.sample', False),
    ('.local-deploy/gui-credentials.json', True),
    ('outputs/private/report.json', True),
    ('evidence/new-run/result.json', True),
    ('evidence/new-run/core.log', True),
    ('evidence/new-run/source.tar.gz', True),
    ('data/session/events.json', True),
    ('state.sqlite3-wal', True), ('state.db-shm', True),
    ('dump.rdb', True), ('capture.pcapng', True),
    ('private.pem', True), ('infra/terraform.tfstate.backup', True),
    ('models/weights.gguf', True), ('models.override.yml', True),
    ('src/chronos/dashboard/target/debug/dashboard', True),
    ('src/chronos/dashboard/Cargo.lock', False),
    ('package-lock.json', False), ('yarn.lock', False),
    ('src/chronos/core/audit_spool.py', False),
    ('src/chronos/core/secrets_policy.py', False),
    ('tests/validation/test_password_auth.py', False),
    ('src/chronos/models/schema.py', False),
    ('config/generation_policy.yaml', False),
    ('compose.azure-staging.yml', False), ('Dockerfile.postgres', False),
    ('.github/workflows/ci.yml', False), ('docs/STATUS.md', False),
])
def test_gitignore_contract(path, ignored):
    root = Path(__file__).resolve().parents[2]
    if not (root / '.git').exists():
        pytest.skip('Git ignore behavior requires a checkout, not a source archive')
    result = subprocess.run(
        ['git', '-c', 'core.excludesFile=/dev/null', 'check-ignore',
         '--no-index', '--quiet', path], cwd=root, capture_output=True,
    )
    assert result.returncode in (0, 1), result.stderr.decode()
    assert (result.returncode == 0) is ignored, path
