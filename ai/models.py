import numpy as np
import pandas as pd
import joblib
import os
import logging
from typing import Dict, Any, Optional, List
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """
    Extracts numerical features from AttackerContext for ML models.
    """
    
    @staticmethod
    def vectorize(context_data: Dict[str, Any]) -> np.ndarray:
        """
        Convert attacker context dictionary to feature vector.
        Expected features:
        0. Session Duration (log seconds)
        1. Command Rate (cmds/min)
        2. Reconnaissance Ratio (recon_cmds / total)
        3. Error Ratio (error_cmds / total) - Placeholder if not tracked directly
        4. Unique Commands Count
        5. Max Recursion Depth (from PST prediction if available)
        6. Lateral Movement Indicator (0 or 1)
        """
        # Safe extraction with defaults
        duration = max(context_data.get("session_duration", 0.0), 1.0)
        cmd_count = context_data.get("command_count", 0)
        behavior_patterns = context_data.get("behavior_patterns", [])
        
        # 0. Session Duration (Log scale to normalize outliers)
        feat_duration = np.log1p(duration)
        
        # 1. Command Rate
        feat_cmd_rate = cmd_count / (duration / 60.0)
        
        # 2. Reconnaissance Ratio (Estimated from patterns)
        # In a real implementation, we'd count specific command types.
        # Here we use a heuristic based on presence of patterns.
        has_recon = 1.0 if "reconnaissance" in behavior_patterns else 0.0
        
        # 3. Lateral Movement
        has_lateral = 1.0 if "lateral_movement" in behavior_patterns else 0.0
        
        # 4. Privilege Escalation
        has_priv_esc = 1.0 if "privilege_escalation" in behavior_patterns else 0.0

        # 5. Data Exfiltration
        has_exfil = 1.0 if "data_exfiltration" in behavior_patterns else 0.0
        
        # 6. Interaction Pattern Count
        pattern_count = len(behavior_patterns)
        
        return np.array([
            feat_duration,
            feat_cmd_rate,
            has_recon,
            has_lateral,
            has_priv_esc,
            has_exfil,
            pattern_count
        ]).reshape(1, -1)

class BehavioralClassifier:
    """
    Random Forest Classifier for Attacker Profiling (Layer 2).
    """
    
    def __init__(self, model_path: str = "ai/data/behavioral_model.pkl"):
        self.model_path = model_path
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.is_trained = False
        self.classes_ = ["script_kiddie", "automated_bot", "apt", "curious_user"]
        
        # Try to load existing model
        self.load_model()
        
    def train(self, X: np.ndarray, y: List[str]):
        """Train the model on feature matrix X and labels y"""
        self.model.fit(X, y)
        self.is_trained = True
        self.classes_ = self.model.classes_
        self.save_model()
        logger.info(f"Behavioral Classifier trained on {len(X)} samples.")
        
    def predict(self, features: np.ndarray) -> Dict[str, float]:
        """
        Return probability distribution over classes.
        Returns: Dict[class_name, probability]
        """
        if not self.is_trained:
            # Fallback for cold start
            return {c: 1.0/len(self.classes_) for c in self.classes_}
            
        try:
            probs = self.model.predict_proba(features)[0]
            return {cls: prob for cls, prob in zip(self.classes_, probs)}
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {}

    def save_model(self):
        """Persist model to disk"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def load_model(self):
        """Load model from disk if exists"""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                self.classes_ = self.model.classes_
                logger.info("Loaded persisted Behavioral Classifier.")
            except Exception as e:
                logger.warning(f"Failed to load model, starting fresh: {e}")
        else:
            logger.info("No existing model found, initializing fresh.")

    def mock_train(self):
        """
        Train a mock model to ensure we have something working immediately (Cold Start).
        Simulates different attacker profiles.
        """
        # Synthetic Data
        # Format: [duration_log, cmd_rate, recon, lateral, priv, exfil, count]
        
        X = [
            # Script Kiddie: Short, fast, loud (recon + priv esc)
            [np.log1p(30), 20.0, 1, 0, 1, 0, 2],
            [np.log1p(60), 15.0, 1, 0, 1, 0, 2],
            
            # Bot: Very fast, repetitive, specific patterns
            [np.log1p(5), 60.0, 1, 0, 0, 0, 1],
            [np.log1p(10), 100.0, 1, 0, 0, 0, 1],

            # APT: Slow, low and slow, lateral movement, exfil
            [np.log1p(600), 2.0, 1, 1, 0, 1, 3],
            [np.log1p(1200), 1.0, 1, 1, 1, 1, 4],
            
            # Curious User: Wandering, low intent
            [np.log1p(180), 5.0, 1, 0, 0, 0, 1],
            [np.log1p(300), 3.0, 0, 0, 0, 0, 0],
        ]
        
        y = [
            "script_kiddie", "script_kiddie",
            "automated_bot", "automated_bot",
            "apt", "apt",
            "curious_user", "curious_user"
        ]
        
        self.train(np.array(X), y)
