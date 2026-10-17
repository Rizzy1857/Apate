from pathlib import Path


def test_private_deployment_and_operator_outputs_are_not_build_context():
    root = Path(__file__).resolve().parents[2]
    patterns = {line.strip() for line in (root / '.dockerignore').read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#')}
    # Guard explicit build-context exclusions, not just Docker COPY choices.
    assert {'.git', '.env', '.env.*', '.local-deploy', 'outputs'} <= patterns
