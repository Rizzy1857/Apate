import pytest
import threading
import time
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor
from chronos.intelligence.orchestrator import GenerationOrchestrator
from chronos.intelligence.provenance import ProvenanceRecord, GenerationSource
from chronos.intelligence.artifact_policy import ArtifactPolicy
from chronos.intelligence.ubuntu_profile import UbuntuProfile

class MockRedis:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()
        
    def set(self, key, value, nx=False, ex=None):
        with self.lock:
            if nx and key in self.data:
                return False
            self.data[key] = value
            return True
            
    def get(self, key):
        with self.lock:
            return self.data.get(key)
            
    def hgetall(self, key):
        with self.lock:
            return self.data.get(key, {})
            
    def lpush(self, key, *values):
        with self.lock:
            if key not in self.data:
                self.data[key] = []
            for v in values:
                self.data[key].insert(0, v)
                
    def ltrim(self, key, start, end):
        with self.lock:
            if key in self.data:
                self.data[key] = self.data[key][start:end+1]
            
    def delete(self, key):
        with self.lock:
            if key in self.data:
                del self.data[key]

    def hset(self, key, mapping):
        with self.lock:
            if key not in self.data:
                self.data[key] = {}
            self.data[key].update(mapping)

    def incr(self, key):
        with self.lock:
            val = self.data.get(key, 0)
            val += 1
            self.data[key] = val
            return val
            
    def expire(self, key, ttl):
        pass

def test_orchestrator_thundering_herd():
    """
    Stress test GenerationOrchestrator to ensure that 500 concurrent requests 
    for the exact same file only invoke the underlying LLM logic exactly ONCE,
    using the Redis dedup locks (nx=True).
    """
    mock_redis = MockRedis()
    mock_profile = UbuntuProfile()
    
    orchestrator = GenerationOrchestrator(
        redis_client=mock_redis,
        profile=mock_profile,
        max_workers=5
    )
    
    # Mock inference runtime
    call_count = 0
    lock = threading.Lock()
    
    def fake_generate(*args, **kwargs):
        nonlocal call_count
        with lock:
            call_count += 1
        time.sleep(0.1) # Simulate generation time
        return "fake_content"
        
    orchestrator.runtime.generate = fake_generate
    
    class MockPolicy:
        skip_generation = False
        model = "llama3:8b"
        category = "valid"
        file_class = "config"
        max_lines = 80
        max_entries = 0
        max_days = 0
        validation_strictness = "high"
        regeneration = "static"
        prompt_template = None
    orchestrator.policy_engine.resolve = MagicMock(return_value=MockPolicy())

    # Mock quota
    orchestrator._check_and_decrement_quota = MagicMock(return_value=True)
    
    # Mock fallback to see if it's hit
    orchestrator.fallback_provider.get_degraded_content = MagicMock(return_value=b"FALLBACK")
    
    # Mock persist empty to see if it's hit
    orchestrator._persist_empty = MagicMock()
    
    # Mock validator
    class FakeResult:
        accepted = True
    orchestrator.validator.validate = MagicMock(return_value=FakeResult())
    
    machine_state = {}
    
    results = []
    
    def fire_request():
        try:
            start_req = time.time()
            res = orchestrator.get_or_generate(
                inode=100,
                path="/etc/passwd",
                session_id="session123",
                machine_state=machine_state
            )
            dur = time.time() - start_req
            results.append((res, dur))
        except Exception as e:
            results.append((e, 0.0))

    # Launch 500 concurrent threads requesting the exact same inode
    threads = [threading.Thread(target=fire_request) for _ in range(500)]
    
    start = time.time()
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start
    
    # Verify that all 500 threads received the successful content bytes
    assert len(results) == 500
    failed_results = [r for r, dur in results if r != b"fake_content"]
    assert not failed_results, f"Some threads did not receive 'fake_content': {failed_results[:5]}"
    
    # MOST IMPORTANTLY: The underlying generation should have only been called ONCE
    assert call_count == 1
    
    print(f"\n[Stress] 500 threads resolved single cache miss in {duration:.2f}s with EXACTLY 1 generation call.")
