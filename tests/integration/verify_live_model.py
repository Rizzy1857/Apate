"""Explicit opt-in local-model check; uses no attacker history or real secrets."""
import os
import time
from chronos.intelligence.inference import InferenceRuntime
from chronos.intelligence.artifact_policy import ArtifactPolicy
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.validator import SemanticValidator


model = os.environ['CHRONOS_TEST_MODEL']
policy = ArtifactPolicy('notes_file', 'notes', 15, None, None, 'high', 'static', model)
runtime = InferenceRuntime()
machine = UbuntuProfile().build_machine_state()
start = time.monotonic()
content = runtime.generate(
    'Output only this short Ubuntu admin note: Check nginx access logs before rotating them.',
    system_prompt='Return plain file contents only. No markdown or commentary.',
    model=model, max_tokens=60)
result = SemanticValidator().validate(content, policy, machine)
assert result.accepted, result.reason
assert 'nginx' in content.lower() and len(content.encode()) <= 65536
print(f'PASS: installed model {model}, validated note, elapsed={time.monotonic()-start:.2f}s')
