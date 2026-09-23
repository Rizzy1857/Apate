import subprocess
from unittest.mock import Mock
import pytest
from chronos.intelligence.inference import InferenceRuntime, ModelUnreachableError


def test_deadline_kills_and_reaps_transport(monkeypatch):
    process = Mock()
    process.communicate.side_effect = [subprocess.TimeoutExpired('transport', .1), (b'', b'')]
    process.poll.return_value = None
    monkeypatch.setattr(subprocess, 'Popen', Mock(return_value=process))
    runtime = InferenceRuntime()
    with pytest.raises(ModelUnreachableError):
        runtime.generate('trusted', timeout=.1)
    process.kill.assert_called_once()
    assert process.communicate.call_count == 2
    assert runtime.circuit_breaker.models['llama3:8b'].failures == 1


def test_completed_transport_records_success(monkeypatch):
    process = Mock(returncode=0)
    process.communicate.return_value = (b'"ready"', b'')
    process.poll.return_value = 0
    monkeypatch.setattr(subprocess, 'Popen', Mock(return_value=process))
    runtime = InferenceRuntime()
    assert runtime.generate('trusted') == 'ready'
    process.kill.assert_not_called()
    assert runtime.circuit_breaker.models['llama3:8b'].successes == 1
