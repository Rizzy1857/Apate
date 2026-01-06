import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend/app')))

from backend.app.ai.engine import AIEngine, ResponseType

TEST_IP = "192.168.1.100"

async def test_correlation():
    print("--- Testing Cross-Protocol Correlation ---")
    
    engine = AIEngine()
    
    # 1. Simulate HTTP Brute Force (Weak Password Attack)
    print("1. Simulating HTTP Brute Force...")
    context_http = {
        "username": "admin",
        "password": "password123",
        "session_history": []
    }
    
    # We need to manually simulate updating the context because generate_response does it implicitly
    # Let's call generate_response to trigger the update
    await engine.generate_response(ResponseType.HTTP_LOGIN, context_http, TEST_IP, "session_http_1")
    
    # Check context
    ctx = engine.attacker_contexts[TEST_IP]
    print(f"   Patterns after HTTP: {ctx.behavior_patterns}")
    print(f"   Score: {ctx.get_threat_score()}")
    assert "weak_password_attack" in ctx.behavior_patterns
    
    # 2. Simulate SSH Reconnaissance from SAME IP
    print("2. Simulating SSH Reconnaissance (Same IP)...")
    context_ssh = {
        "command": "whoami",
        "session_history": ["ls", "pwd"]
    }
    await engine.generate_response(ResponseType.SSH_COMMAND, context_ssh, TEST_IP, "session_ssh_1")
    
    # Check context again
    print(f"   Patterns after SSH: {ctx.behavior_patterns}")
    score = ctx.get_threat_score()
    print(f"   Risk Score: {score}")
    
    assert "reconnaissance" in ctx.behavior_patterns
    assert "weak_password_attack" in ctx.behavior_patterns
    # Score expectations:
    # 1. Weak Pass (10.0 * 1.0) = 10.0. Multiplier becomes 1.5.
    # 2. Recon (5.0 * 1.5) = 7.5. Total = 17.5.
    assert score >= 17.0
    
    # 3. Trigger risk multiplier
    print("3. Triggering Lateral Movement...")
    context_ssh_lat = {
        "command": "ssh user@10.0.0.2",
        "session_history": ["ls", "pwd", "whoami"]
    }
    await engine.generate_response(ResponseType.SSH_COMMAND, context_ssh_lat, TEST_IP, "session_ssh_1")
    
    print(f"   Patterns: {ctx.behavior_patterns}")
    score_final = ctx.get_threat_score()
    print(f"   Final Risk Score: {score_final}")
    
    # 3. Lateral (15.0 * 1.5) = 22.5. (+ previous 17.5) = 40.0.
    assert score_final >= 40.0
    
    print("✅ Correlation Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_correlation())
