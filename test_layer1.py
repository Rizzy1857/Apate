import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ai.engine import MarkovPredictor

def test_markov_prediction():
    print("Initializing Markov Predictor (PST + Kneser-Ney)...")
    predictor = MarkovPredictor(max_order=2, smoothing=0.5)
    
    # Training Data: Simple repeating pattern
    # Pattern: ls -> cd -> ls -> cat
    sequence = ["ls", "cd", "ls", "cat", "ls", "cd", "ls", "cat", "ls", "cd"]
    
    print(f"Training on sequence: {sequence}")
    predictor.learn_sequence(sequence)
    
    # Test Case 1: Predict after 'ls'
    # Should be 'cd' (seen 3 times) or 'cat' (seen 2 times) depending on context
    # Context: ls -> ?
    res1 = predictor.predict_next(["ls"])
    print(f"\n[Test 1] History: ['ls']")
    print(f"Predicted: {res1.predicted} (Confidence: {res1.confidence:.2f})")
    print(f"Distribution: {res1.distribution}")
    
    assert res1.predicted == "cd", f"Expected 'cd', got {res1.predicted}"
    
    # Test Case 2: Predict after 'ls', 'cd'
    # Should be 'ls'
    res2 = predictor.predict_next(["ls", "cd"])
    print(f"\n[Test 2] History: ['ls', 'cd']")
    print(f"Predicted: {res2.predicted} (Confidence: {res2.confidence:.2f})")
    
    assert res2.predicted == "ls", f"Expected 'ls', got {res2.predicted}"
    
    # Test Case 3: Zero-Frequency / Unseen context
    # History: ['unknown_cmd']
    res3 = predictor.predict_next(["unknown_cmd"])
    print(f"\n[Test 3] History: ['unknown_cmd']")
    print(f"Predicted: {res3.predicted}")
    
    assert res3.predicted is None, "Expected None for unknown context"
    
    print("\n✅ Verification Passed: PST implementation is functional.")

if __name__ == "__main__":
    test_markov_prediction()
