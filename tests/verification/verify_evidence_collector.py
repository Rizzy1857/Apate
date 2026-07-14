import sys
import os
import time
import uuid
import json
from datetime import datetime, timedelta, timezone
import threading

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from chronos.watcher.evidence_collector import EvidenceCollector
from chronos.core.persistence import PersistenceLayer

class MockStreamer:
    def __init__(self):
        self.subscribers = []
    
    def subscribe(self, callback):
        self.subscribers.append(callback)
        
    def emit(self, event):
        for sub in self.subscribers:
            sub(event)

class MockPersistence:
    def __init__(self):
        self.evidence_data = {}
        
    def flush_evidence(self, session_id, data):
        self.evidence_data[session_id] = data

def test_evidence_collector():
    print("============================================================")
    print("Phase M2.F — Evidence Collector Verification")
    print("============================================================")
    
    streamer = MockStreamer()
    persistence = MockPersistence()
    
    collector = EvidenceCollector(streamer, persistence)
    
    # Clean up any previous test data in redis
    collector.redis.delete("chronos:evidence:test_session_abc123")
    
    session_id = "test_session_abc123"
    start_time = datetime.now(timezone.utc)
    
    events = [
        {
            "session_id": session_id,
            "operation": "ssh_command",
            "timestamp": start_time.isoformat(),
            "metadata": {"command": "whoami"}
        },
        {
            "session_id": session_id,
            "operation": "read",
            "timestamp": (start_time + timedelta(seconds=1)).isoformat(),
            "path": "/etc/passwd"
        },
        {
            "session_id": session_id,
            "operation": "readdir",
            "timestamp": (start_time + timedelta(seconds=2)).isoformat(),
            "path": "/etc/nginx"
        },
        {
            "session_id": session_id,
            "operation": "ssh_command",
            "timestamp": (start_time + timedelta(seconds=3)).isoformat(),
            "metadata": {"command": "cat /etc/shadow"}
        },
        {
            "session_id": session_id,
            "operation": "ssh_disconnect",
            "timestamp": (start_time + timedelta(seconds=10)).isoformat(),
        }
    ]
    
    for event in events:
        streamer.emit(event)
        
    # Check what was flushed to persistence
    assert session_id in persistence.evidence_data, "Evidence was not flushed to persistence"
    
    flushed = persistence.evidence_data[session_id]
    
    print("\n[Evidence Collector Results]")
    print(f"  Duration: {flushed['duration_seconds']}s")
    print(f"  Detection Status: {flushed['detection_status']}")
    print(f"  First Suspicious: {flushed['first_suspicious_command']}")
    print(f"  Commands: {len(flushed['commands'])}")
    print(f"  Visited Files: {flushed['visited_files']}")
    
    assert flushed['duration_seconds'] == 10, "Duration incorrect"
    assert flushed['detection_status'] == 'detected', "Did not detect 'whoami' as suspicious"
    assert flushed['first_suspicious_command'] == 'whoami', "First suspicious command incorrect"
    assert len(flushed['commands']) == 2, "Should have 2 commands"
    assert "/etc/passwd" in flushed['visited_files'], "Missing visited file"
    assert "/etc/nginx" in flushed['visited_files'], "Missing visited file"
    
    # Check redis cleanup
    assert not collector.redis.exists(f"chronos:evidence:{session_id}"), "Redis key not cleaned up"
    
    print("\n[SUCCESS] Evidence Collector Verified")
    
if __name__ == "__main__":
    test_evidence_collector()
