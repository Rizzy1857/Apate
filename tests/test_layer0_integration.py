
import pytest
import time

# Skip if rust_protocol is not built/installed
try:
    import rust_protocol
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False

@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust protocol library not available")
def test_detect_threats_return_type():
    """Verify detect_threats returns a dict (not string) and has expected keys."""
    
    # Safe payload
    result = rust_protocol.detect_threats("GET / HTTP/1.1", "127.0.0.1")
    # Might be None if no noise/threat
    # Noise detector has "masscan", "nmap" etc.
    
    # Noise payload
    noise_payload = "masscan"
    result_noise = rust_protocol.detect_threats(noise_payload, "127.0.0.1")
    assert isinstance(result_noise, dict)
    assert result_noise["is_noise"] is True
    assert result_noise["protocol"] == "unknown" # masscan string isn't HTTP/SSH
    
    # Threat payload
    threat_payload = "cat /etc/passwd; rm -rf /"
    result_threat = rust_protocol.detect_threats(threat_payload, "127.0.0.1")
    assert isinstance(result_threat, dict)
    assert result_threat["threat_detected"] is True
    assert result_threat["event_type"] == "command_injection"
    assert "severity" in result_threat

if __name__ == "__main__":
    if RUST_AVAILABLE:
        test_detect_threats_return_type()
        print("✅ Layer 0 Integration Test Passed")
    else:
        print("⚠️ Rust protocol not available, skipping test")
