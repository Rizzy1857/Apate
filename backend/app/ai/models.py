"""
Layer 2: Reasoning Layer Models
-------------------------------
Machine Learning models for behavioral classification and threat profiling.
Currently implements a Random Forest classifier with manual feature extraction.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not found. Layer 2 will operate in heuristic mode.")

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """Extract numerical features from AttackerContext for ML classification"""
    
    @staticmethod
    def vectorize(context_data: Dict[str, Any]) -> np.ndarray:
        """
        Convert attacker behavior to feature vector.
        
        Args:
            context_data: Dictionary containing:
                - session_duration (float): Seconds since first seen
                - command_count (int): Total commands executed
                - behavior_patterns (List[str]): "reconnaissance", "lateral_movement", etc.
                - threat_level (str): "low", "medium", "high", "critical"
                
        Returns:
            np.ndarray: 1D array of features (reshaped to 1xN for prediction)
        """
        # Safely get values with defaults
        duration = context_data.get("session_duration", 0.0)
        cmd_count = context_data.get("command_count", 0)
        patterns = context_data.get("behavior_patterns", [])
        
        # Feature 0: Session duration (log scale to handle heavy tails)
        feat_duration = np.log1p(duration)
        
        # Feature 1: Command execution rate (commands/minute)
        # Avoid division by zero
        minutes = max(duration / 60.0, 0.01)
        feat_cmd_rate = cmd_count / minutes
        
        # Feature 2-5: Behavior Pattern Indicators (One-Hot-like)
        has_recon = 1.0 if "reconnaissance" in patterns else 0.0
        has_lateral = 1.0 if "lateral_movement" in patterns else 0.0
        has_priv_esc = 1.0 if "privilege_escalation" in patterns else 0.0
        has_exfil = 1.0 if "data_exfiltration" in patterns else 0.0
        
        # Feature 6: Total behavior pattern count severity
        pattern_count = float(len(patterns))
        
        features = np.array([
            feat_duration,
            feat_cmd_rate,
            has_recon,
            has_lateral,
            has_priv_esc,
            has_exfil,
            pattern_count
        ], dtype=np.float64)
        
        return features.reshape(1, -1)


class BehavioralClassifier:
    """
    Random Forest classifier for attacker profiling.
    Classifies attackers into categories: script_kiddie, automated_bot, apt, curious_user.
    """
    
    def __init__(self):
        if SKLEARN_AVAILABLE:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42
            )
        else:
            self.model = None
            
        self.is_trained = False
        self.classes_ = ["script_kiddie", "automated_bot", "apt", "curious_user"]
    
    def predict(self, features: np.ndarray) -> Dict[str, float]:
        """
        Predict attacker class probabilities.
        
        Args:
            features: 1xN numpy array from FeatureExtractor
            
        Returns:
            Dictionary mapping class names to probabilities
             e.g. {"script_kiddie": 0.8, "apt": 0.2, ...}
        """
        if not SKLEARN_AVAILABLE or not self.is_trained or self.model is None:
            return {}
            
        try:
            # predict_proba returns [ [p1, p2, p3, p4] ]
            probas = self.model.predict_proba(features)[0]
            
            # Map classes to probabilities
            result = {}
            for i, class_name in enumerate(self.model.classes_):
                result[class_name] = float(probas[i])
                
            return result
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {}
            
    def mock_train(self):
        """
        Initialize classifier with synthetic training data (Cold Start).
        This allows Layer 2 to function before real-world data is collected.
        """
        if not SKLEARN_AVAILABLE or self.model is None:
            return
            
        logger.info("Training Layer 2 model with synthetic data (Cold Start)...")
        
        # DEFINITION OF SYNTHETIC PROFILES
        # Feature order: [duration_log, cmd_rate, recon, lateral, priv, exfil, pattern_count]
        
        X_train = []
        y_train = []
        
        # 1. Script Kiddie: Fast, loud, clumsy (Recon + PrivEsc)
        # Short duration, high rate
        for _ in range(5):
            X_train.append([np.log1p(30), 20.0, 1.0, 0.0, 1.0, 0.0, 2.0])
            y_train.append("script_kiddie")
            
        # 2. Automated Bot: Very fast, specific repetitive task (Recon only)
        # Ultra short duration, ultra high rate
        for _ in range(5):
            X_train.append([np.log1p(5), 60.0, 1.0, 0.0, 0.0, 0.0, 1.0])
            y_train.append("automated_bot")
            
        # 3. APT (Advanced Persistent Threat): Slow, low-and-slow, specific goals (Lateral + Exfil)
        # Long duration, low rate
        for _ in range(5):
            X_train.append([np.log1p(600), 2.0, 1.0, 1.0, 0.0, 1.0, 3.0])
            y_train.append("apt")
            
        # 4. Curious User / Researcher: Wandering, random commands
        # Medium duration, medium rate, low pattern trigger
        for _ in range(5):
            X_train.append([np.log1p(180), 5.0, 1.0, 0.0, 0.0, 0.0, 1.0])
            y_train.append("curious_user")
            
        try:
            self.model.fit(X_train, y_train)
            self.is_trained = True
            logger.info(f"Layer 2 model trained on {len(X_train)} synthetic samples.")
        except Exception as e:
            logger.error(f"Failed to train Layer 2 model: {e}")
