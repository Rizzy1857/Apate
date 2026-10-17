from chronos.intelligence.artifact_policy import ArtifactPolicyEngine
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.validator import SemanticValidator


def test_history_rejects_terminal_prompts_but_accepts_commands():
    machine = UbuntuProfile().build_machine_state()
    machine['artifact_path'] = '/home/ubuntu/.bash_history'
    policy = ArtifactPolicyEngine().resolve('.bash_history', machine['artifact_path'], machine)
    policy.category = 'active'  # Do not randomly exercise the empty-file policy.
    validator = SemanticValidator()
    for content in ('root@web01:~# sudo apt-get update',
                    'ubuntu@web01:~$ pwd', '$ pwd', '# pwd'):
        result = validator.validate(content, policy, machine)
        assert not result.accepted
        assert result.reason.startswith('history:')
    assert validator.validate('pwd\nsudo apt-get update\nls -la\n', policy, machine).accepted
