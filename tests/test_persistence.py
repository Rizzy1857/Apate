import sys
import os
import shutil
import asyncio
from typing import List

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend/app')))


from backend.app.ai.engine import AIEngine, AIProvider

TEST_STORAGE_PATH = "data/test_ai_models"

def cleanup():
    if os.path.exists(TEST_STORAGE_PATH):
        shutil.rmtree(TEST_STORAGE_PATH)

async def test_persistence():
    print("--- Testing Persistence ---")
    cleanup()
    
    # 1. Initialize Engine and learn something
    print("1. Initializing Engine and training...")
    engine = AIEngine(storage_path=TEST_STORAGE_PATH)
    
    # Train SSH predictor
    seq1 = ["ls", "pwd", "whoami"]
    seq2 = ["ls", "cd", "cat"]
    
    engine.predictors["ssh"].learn_sequence(seq1)
    engine.predictors["ssh"].learn_sequence(seq2)
    
    # Verify it learned
    pred_res = engine.predictors["ssh"].predict_next(["ls"])
    print(f"   Prediction for 'ls': {pred_res.predicted} (Confidence: {pred_res.confidence:.2f})")
    assert pred_res.predicted in ["pwd", "cd"]
    
    # 2. Save State
    print("2. Saving state...")
    engine.save_state()
    
    # 3. Explicit Shutdown
    print("3. Shutting down Engine (saving state)...")
    engine.shutdown()
    del engine
    
    # 4. Re-initialize Engine
    print("4. Re-initializing Engine from disk...")
    # New engine instance
    engine2 = AIEngine(storage_path=TEST_STORAGE_PATH)
    
    # 5. Verify Memory
    print("5. Verifying memory persistence...")
    pred_res2 = engine2.predictors["ssh"].predict_next(["ls"])
    print(f"   Prediction for 'ls': {pred_res2.predicted} (Confidence: {pred_res2.confidence:.2f})")
    
    assert pred_res2.predicted == pred_res.predicted
    assert pred_res2.confidence == pred_res.confidence
    
    print("✅ Persistence Test Passed!")
    cleanup()

if __name__ == "__main__":
    asyncio.run(test_persistence())
