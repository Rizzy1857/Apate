
import pytest
from backend.app.ai.engine import MarkovPredictor, SymbolTable

def test_markov_predictor_whitelist():
    """Verify that whitelist filters out candidates correctly."""
    predictor = MarkovPredictor(max_order=1)
    
    # Train: "ls" -> "rm_rf" (dangerous command) - DOMINANT
    for _ in range(10):
        predictor.learn_sequence(["ls", "rm_rf"])
    
    # Train: "ls" -> "safe_cmd" - MINOR
    predictor.learn_sequence(["ls", "safe_cmd"])
    
    # Without whitelist, it should predict "rm_rf"
    pred_no_guard = predictor.predict_next(["ls"])
    assert pred_no_guard.predicted == "rm_rf"
    
    # With whitelist containing only "safe_cmd", it should predict "safe_cmd"
    # or return None if "safe_cmd" probability is too low (but Kneser-Ney should give it some prob)
    # Actually, if we filter candidates, "safe_cmd" is the only valid candidate.
    whitelist = {"safe_cmd", "ls"}
    pred_guarded = predictor.predict_next(["ls"], whitelist=whitelist)
    
    print(f"DEBUG: predicted={pred_guarded.predicted}, dist={pred_guarded.distribution}")
    assert pred_guarded.predicted == "safe_cmd"
    assert "rm_rf" not in pred_guarded.distribution

def test_service_separation_logic():
    """
    Verify that we can maintain independent predictors.
    This mimics the logic in AIEngine where we have selectors["ssh"] and selectors["http"].
    """
    predictors = {
        "ssh": MarkovPredictor(max_order=1),
        "http": MarkovPredictor(max_order=1)
    }
    
    # Train SSH: "connect" -> "auth"
    predictors["ssh"].learn_sequence(["connect", "auth"])
    
    # Train HTTP: "GET" -> "200_OK"
    predictors["http"].learn_sequence(["GET", "200_OK"])
    
    # Predict on SSH with "connect" -> should be "auth"
    ssh_res = predictors["ssh"].predict_next(["connect"])
    assert ssh_res.predicted == "auth"
    
    # Predict on HTTP with "connect" -> should be None (unknown symbol/context)
    http_res = predictors["http"].predict_next(["connect"])
    assert http_res.predicted is None
    
    # Predict on HTTP with "GET" -> should be "200_OK"
    http_res2 = predictors["http"].predict_next(["GET"])
    assert http_res2.predicted == "200_OK"

if __name__ == "__main__":
    # Manually run tests if executed primarily
    try:
        test_markov_predictor_whitelist()
        print("✅ test_markov_predictor_whitelist passed")
        test_service_separation_logic()
        print("✅ test_service_separation_logic passed")
    except AssertionError as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Test failed: {e}")
        exit(1)
