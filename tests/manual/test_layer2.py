import os
import numpy as np

from backend.app.ai.models import FeatureExtractor, BehavioralClassifier
from backend.app.ai.engine import AIEngine, AIProvider

def test_layer2_components():
    print("Initializing Layer 2 Components...")
    
    # 1. Test Feature Extractor
    print("\n[Test 1] Feature Extraction")
    mock_context = {
        "session_duration": 120.0,
        "command_count": 10,
        "behavior_patterns": ["reconnaissance", "lateral_movement"],
        "threat_level": "unknown"
    }
    
    features = FeatureExtractor.vectorize(mock_context)
    print(f"Features shape: {features.shape}")
    print(f"Features: {features}")
    
    assert features.shape == (1, 7), "Feature vector should be 1x7"
    assert features[0, 2] == 1.0, "Should have reconnaissance flag"
    assert features[0, 3] == 1.0, "Should have lateral movement flag"
    
    # 2. Test Classifier
    print("\n[Test 2] Behavioral Classifier (Mock Train)")
    clf = BehavioralClassifier(model_path="test_model.pkl")
    clf.mock_train()
    
    print("Predicting on mock context...")
    preds = clf.predict(features)
    print(f"Predictions: {preds}")
    
    assert len(preds) > 0, "Should return predictions"
    assert "script_kiddie" in preds, "Should contain class labels"
    
    # Clean up
    if os.path.exists("test_model.pkl"):
        os.remove("test_model.pkl")
        
    print("\n✅ Verification Passed: Layer 2 ML components are functional.")

if __name__ == "__main__":
    test_layer2_components()
