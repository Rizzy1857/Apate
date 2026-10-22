from pathlib import Path
import re
import runpy
import yaml


def test_private_deployment_and_operator_outputs_are_not_build_context():
    root = Path(__file__).resolve().parents[2]
    patterns = {line.strip() for line in (root / '.dockerignore').read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#')}
    # Guard explicit build-context exclusions, not just Docker COPY choices.
    assert {'.git', '.env', '.env.*', '.local-deploy', 'outputs'} <= patterns


def test_compose_ci_provides_every_required_configuration_secret():
    root = Path(__file__).resolve().parents[2]
    required = set(re.findall(r'\$\{([A-Z_]+):\?', (root / 'docker-compose.yml').read_text()))
    workflow = yaml.safe_load((root / '.github/workflows/ci.yml').read_text())
    checks = [step for step in workflow['jobs']['python']['steps']
              if step.get('run') == 'docker compose config --quiet']
    assert checks
    for step in checks:
        assert required <= step.get('env', {}).keys()
        assert all(step['env'][name] for name in required)


def test_azure_staging_is_standalone_private_and_immutable():
    root = Path(__file__).resolve().parents[2]
    assert '.env.azure' in (root / '.gitignore').read_text().splitlines()
    stack = yaml.safe_load((root / 'compose.azure-staging.yml').read_text())
    services = stack['services']
    assert set(services) == {'core-engine', 'redis-store', 'db-store'}
    assert stack['networks']['research']['internal'] is True
    assert services['core-engine']['ports'] == ['127.0.0.1:2222:2222']
    assert 'ports' not in services['redis-store']
    assert 'ports' not in services['db-store']
    assert '${MIRAGE_IMAGE:?' in services['core-engine']['image']
    assert '${MIRAGE_REDIS_IMAGE:?' in services['redis-store']['image']
    assert '${MIRAGE_POSTGRES_IMAGE:?' in services['db-store']['image']
    for service in services.values():
        assert 'build' not in service
        assert all(not mount.startswith(('.', '/')) for mount in service['volumes'])
    assert services['core-engine']['read_only'] is True
    assert services['core-engine']['tmpfs'] == ['/tmp:rw,noexec,nosuid,size=64m,mode=1777']
    assert services['core-engine']['environment']['CHRONOS_INFERENCE_MODE'] == 'deterministic'
    assert services['core-engine']['environment']['CHRONOS_PERSISTENT_RUNS'] == '1'


def test_release_archive_contains_standalone_deployment_configuration():
    root = Path(__file__).resolve().parents[2]
    freezer = runpy.run_path(str(root / 'tests/integration/freeze_release_candidate.py'))
    assert Path('compose.azure-staging.yml') in freezer['included_files']()
    assert {Path('Dockerfile.redis'), Path('Dockerfile.postgres')} <= set(freezer['included_files']())
    assert (root / 'Dockerfile.redis').read_text().rstrip().endswith('USER redis')
    assert (root / 'Dockerfile.postgres').read_text().rstrip().endswith('USER postgres')
