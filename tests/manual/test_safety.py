import numpy as np

from backend.app.ai.models import FeatureExtractor
from backend.app.ai.engine import MarkovPredictor

def test_safety_mechanisms():
    print("Testing Safety & Stability Mechanisms...")
    
    # 1. Layer 1: Input Sanitization
    print("\n[Test 1] Layer 1: Garbage Input")
    predictor = MarkovPredictor()
    
    # Garbage string with non-printables
    garbage_input = ["ls", "cd\x00\x1f\x7f", "valid_cmd"]
    print(f"Feeding garbage: {garbage_input}")
    
    # Should not crash and strip chars
    predictor.learn_sequence(garbage_input)
    
    # Check what was learned (indirectly via symbol table size)
    # 'ls', 'cd', 'valid_cmd' should be learned
    # 'cd\x00...' should be sanitized to 'cd'
    print(f"Symbol Table Size: {len(predictor.symbol_table)}")
    
    # Predict with huge input
    huge_input = ["A" * 10000]
    res = predictor.predict_next(huge_input)
    print(f"Prediction result on huge input: {res.predicted}")
    assert res.predicted is None, "Should handle huge input gracefully"

    # 2. Layer 2: Feature Normalization
    print("\n[Test 2] Layer 2: NaN/Inf Context")
    bad_context = {
        "session_duration": float('nan'),
        "command_count": float('inf'),
        "behavior_patterns": ["reconnaissance"],
        "threat_level": "unknown"
    }
    
    feats = FeatureExtractor.vectorize(bad_context)
    print(f"Features: {feats}")
    
    assert not np.isnan(feats).any(), "Features should not contain NaN"
    assert not np.isinf(feats).any(), "Features should not contain Inf"
    assert np.max(feats) <= 1e6, "Features should be clipped"
    
    print("\n✅ Verification Passed: Safety mechanisms operational.")

if __name__ == "__main__":
    test_safety_mechanisms()
