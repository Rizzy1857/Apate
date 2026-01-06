import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend/app')))

from backend.app.ai.engine import ComplexityRouter, AttackerContext, ML_AVAILABLE

def test_l2_safeguards():
    print("--- Testing Layer 2 Safeguards ---")
    
    # Mocking ML Availability / Classifier
    # We can pass a mock classifier to check_l2_exit
    mock_classifier = MagicMock()
    mock_classifier.is_trained = True
    # Predicts "Cluster_A" (APT) with high confidence
    mock_classifier.predict.return_value = {"Cluster_A": 0.95, "Cluster_B": 0.05}
    
    # 1. Evidence Gate Test
    print("1. Evidence Gate (Low History)...")
    ctx = AttackerContext("1.2.3.4", "sess1")
    ctx.command_history = ["ls", "whoami"] # only 2 commands
    
    # Check
    result = ComplexityRouter.check_l2_exit(ctx, classifier=mock_classifier)
    
    print(f"   Result: {result} (Should be False)")
    assert result == False
    
    # Ensure risk multiplier wasn't touched
    assert ctx.risk_multiplier == 1.0
    print("   Evidence Gate Passed (No inference ran).")
    
    # 2. Advisory Only Test
    print("2. Advisory Logic (High History)...")
    ctx.command_history = ["ls", "whoami", "cd", "cat", "pwd"] # 5 commands
    
    result = ComplexityRouter.check_l2_exit(ctx, classifier=mock_classifier)
    
    print(f"   Result: {result} (Should be False - Advisory Only)")
    assert result == False
    
    print(f"   Risk Multiplier: {ctx.risk_multiplier}")
    # Should have boosted multiplier
    assert ctx.risk_multiplier == 1.5
    
    print("   Advisory Logic Passed (Multiplier boosted, no block).")
    
    print("✅ Layer 2 Safeguards Test Passed!")

if __name__ == "__main__":
    test_l2_safeguards()
