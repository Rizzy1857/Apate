import pytest
import time
import threading
from unittest.mock import patch, MagicMock
from requests.exceptions import RequestException

from chronos.intelligence.inference import (
    CircuitBreaker, BreakerState, ModelHealth, 
    ModelUnreachableError, InferenceRuntime
)

def test_circuit_breaker_transitions():
    breaker = CircuitBreaker(failure_threshold=3, base_backoff=0.1, max_backoff=1.0)
    
    # 1. Start CLOSED
    assert breaker.can_execute("test_model") == True
    
    # 2. Record 2 failures -> Still CLOSED
    breaker.record_failure("test_model")
    breaker.record_failure("test_model")
    assert breaker._get_health("test_model").state == BreakerState.CLOSED
    assert breaker.can_execute("test_model") == True
    
    # 3. Record 3rd failure -> OPEN
    breaker.record_failure("test_model")
    health = breaker._get_health("test_model")
    assert health.state == BreakerState.OPEN
    assert breaker.can_execute("test_model") == False
    
    # 4. Wait for backoff to expire -> HALF_OPEN on first call
    time.sleep(0.15)  # Wait longer than base_backoff * jitter
    assert breaker.can_execute("test_model") == True
    assert health.state == BreakerState.HALF_OPEN
    
    # 5. Second call while HALF_OPEN should be rejected instantly
    assert breaker.can_execute("test_model") == False
    
    # 6. Record success -> CLOSED
    breaker.record_success("test_model")
    assert health.state == BreakerState.CLOSED
    assert breaker.can_execute("test_model") == True
    assert health.failures == 0
    assert health.successes == 1

def test_circuit_breaker_half_open_thread_safety():
    breaker = CircuitBreaker(failure_threshold=1, base_backoff=0.1)
    
    # Trip breaker
    breaker.record_failure("test_model")
    assert breaker._get_health("test_model").state == BreakerState.OPEN
    
    # Wait for backoff
    time.sleep(0.15)
    
    # Launch multiple threads trying to execute
    allowed_count = 0
    lock = threading.Lock()
    
    def try_execute():
        nonlocal allowed_count
        if breaker.can_execute("test_model"):
            with lock:
                allowed_count += 1
                
    threads = [threading.Thread(target=try_execute) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # Exactly ONE thread should have been allowed through
    assert allowed_count == 1
    assert breaker._get_health("test_model").state == BreakerState.HALF_OPEN

@patch('chronos.intelligence.inference.requests.post')
def test_inference_runtime_integration(mock_post):
    runtime = InferenceRuntime()
    runtime.circuit_breaker = CircuitBreaker(failure_threshold=2, base_backoff=0.1)
    
    # Mock network failure
    mock_post.side_effect = RequestException("Timeout")
    
    with pytest.raises(ModelUnreachableError, match="Ollama unreachable"):
        runtime.generate("test prompt", model="llama3")
        
    with pytest.raises(ModelUnreachableError, match="Ollama unreachable"):
        runtime.generate("test prompt", model="llama3")
        
    # Third request should be short-circuited
    with pytest.raises(ModelUnreachableError, match="Circuit breaker is OPEN"):
        runtime.generate("test prompt", model="llama3")
        
    # Verify requests.post was only called twice!
    assert mock_post.call_count == 2
    
    # Wait for recovery
    time.sleep(0.15)
    
    # Mock success for the probe
    mock_post.side_effect = None
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Success!"}
    mock_post.return_value = mock_response
    
    res = runtime.generate("test prompt", model="llama3")
    assert res == "Success!"
    assert mock_post.call_count == 3
    assert runtime.circuit_breaker._get_health("llama3").state == BreakerState.CLOSED
