import sys
import os
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend/app')))

from backend.app.ai.engine import ThreatAccumulator

def test_threat_scoring():
    print("--- Testing Threat Accumulator ---")
    
    acc = ThreatAccumulator()
    
    # 1. Base Score
    print("1. Initial Score: ", acc.score)
    assert acc.score == 0.0
    
    # 2. Add Event (Reconnaissance = 5.0)
    print("2. Adding 'reconnaissance'...")
    acc.update("reconnaissance")
    print(f"   Score: {acc.score}")
    assert acc.score == 5.0
    
    # 3. Add High Risk Event (Privilege Escalation = 30.0) with Multiplier
    print("3. Adding 'privilege_escalation' with 1.5x multiplier...")
    acc.update("privilege_escalation", multiplier=1.5)
    # Expected: 5.0 + (30.0 * 1.5) = 5.0 + 45.0 = 50.0
    print(f"   Score: {acc.score}")
    # Allow for micro-decay (execution time)
    assert acc.score >= 49.9 and acc.score <= 50.1
    
    # 4. Check Risk Levels
    level, score = acc.get_risk_level()
    print(f"   Risk Level: {level}")
    assert level == "Elevated" # > 20, <= 50? Wait, 50 is transition.
    # Logic: > 50 is High. == 50 is Elevated.
    
    # 5. Decay Test
    # Simulate time passing by modifying last_update
    print("5. Testing Decay...")
    # Mocking time passing: 10 minutes ago
    # Decay rate is 0.5 per minute -> 5 points
    # Need to hack internal state or wait (hacking is better)
    from datetime import datetime, timedelta
    acc.last_update = datetime.utcnow() - timedelta(minutes=10)
    
    # Trigger decay check
    level_decayed, score_decayed = acc.get_risk_level()
    print(f"   Decayed Score: {score_decayed}")
    
    # Expected: 50.0 - (10 * 0.5) = 45.0
    assert score_decayed >= 44.9 and score_decayed <= 45.1
    
    print("✅ Threat Accumulator Test Passed!")

if __name__ == "__main__":
    test_threat_scoring()
