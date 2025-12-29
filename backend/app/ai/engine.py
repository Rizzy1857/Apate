"""
AI Engine - Foundation Layer
----------------------------
This is the foundation AI engine that will be superseded by the Mirage
five-layer cognitive architecture. Currently provides basic stubbed responses
and will serve as the base for Layer 4 (Persona Layer) implementation.

The new architecture uses a **Cascading Short-Circuit** model:
- Layer 0: Rust reflex layer (sub-millisecond deterministic responses)
- Pipeline: Complexity Router checks for exit ramps at each stage
- Layer 1: Intuition layer (HMM command prediction) -> Exit if predicted
- Layer 2: Reasoning layer (ML behavioral classification) -> Exit if known profile
- Layer 3: Strategy layer (RL optimization) -> Exit if standard strategy
- Layer 4: Persona layer (LLM-based responses) -> Only for novel interactions

This engine provides the foundation and will be integrated into the cognitive
director when the full Mirage architecture is implemented.
"""

import asyncio
import logging
import random
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from enum import Enum

# Import Rust protocol for Layer 0 threat detection
try:
    import rust_protocol
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.warning("Rust protocol library not available - Layer 0 disabled")

logger = logging.getLogger(__name__)

# Import Layer 2 Models
try:
    from .models import BehavioralClassifier, FeatureExtractor
    ML_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ML dependencies missing, Layer 2 will use heuristics: {e}")
    ML_AVAILABLE = False

class ResponseType(str, Enum):
    """Types of responses the AI can generate"""
    SSH_COMMAND = "ssh_command"
    HTTP_LOGIN = "http_login"
    SYSTEM_ERROR = "system_error"
    SOCIAL_ENGINEERING = "social_engineering"
    THREAT_ASSESSMENT = "threat_assessment"

class AIProvider(str, Enum):
    """Supported AI providers"""
    STUB = "stub"  # Development stub
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    LOCAL_LLM = "local_llm"
    OLLAMA = "ollama"

class AttackerContext:
    """Context about the attacker for AI personalization"""
    
    def __init__(self, ip: str, session_id: str):
        self.ip = ip
        self.session_id = session_id
        self.first_seen = datetime.utcnow()
        self.last_seen = datetime.utcnow()
        self.command_history: List[str] = []
        self.login_attempts: List[Dict[str, str]] = []
        self.threat_level = "unknown"
        self.behavior_patterns: List[str] = []
        self.geographical_info: Dict[str, Any] = {}
        self.tools_detected: List[str] = []
        self.threat_accum = ThreatAccumulator()
        self.risk_multiplier = 1.0 # Correlation multiplier
        
    def update_activity(self, activity_type: str, data: Dict[str, Any]):
        """Update attacker context with new activity"""
        self.last_seen = datetime.utcnow()
        
        if activity_type == "ssh_command":
            self.command_history.append(data.get("command", ""))
            self._analyze_command_patterns(data.get("command", ""))
        elif activity_type == "login_attempt":
            self.login_attempts.append(data)
            self._analyze_login_patterns(data)
    
    def _analyze_command_patterns(self, command: str):
        """Analyze command patterns to understand attacker behavior"""
        reconnaissance_commands = ["ls", "ps", "netstat", "ifconfig", "whoami", "id", "uname"]
        lateral_movement = ["ssh", "scp", "rsync", "ping"]
        persistence = ["crontab", "systemctl", "service", "chkconfig"]
        data_exfiltration = ["wget", "curl", "nc", "socat", "tar", "zip"]
        
        if command.split()[0].lower() in reconnaissance_commands:
            if "reconnaissance" not in self.behavior_patterns:
                self.behavior_patterns.append("reconnaissance")
                self.threat_accum.update("reconnaissance", self.risk_multiplier)
        elif command.split()[0].lower() in lateral_movement:
            if "lateral_movement" not in self.behavior_patterns:
                self.behavior_patterns.append("lateral_movement")
                self.threat_accum.update("lateral_movement", self.risk_multiplier)
        elif command.split()[0].lower() in persistence:
            if "persistence" not in self.behavior_patterns:
                self.behavior_patterns.append("persistence")
                self.threat_accum.update("persistence", self.risk_multiplier)
        elif command.split()[0].lower() in data_exfiltration:
            if "data_exfiltration" not in self.behavior_patterns:
                self.behavior_patterns.append("data_exfiltration")
                self.threat_accum.update("data_exfiltration", self.risk_multiplier)
    
    def _analyze_login_patterns(self, login_data: Dict[str, Any]):
        """Analyze login patterns for threat assessment"""
        username = login_data.get("username", "").lower()
        password = login_data.get("password", "").lower()
        
        # Check for common attack patterns
        if username in ["admin", "administrator", "root"]:
            if "privilege_escalation" not in self.behavior_patterns:
                self.behavior_patterns.append("privilege_escalation")
                self.threat_accum.update("privilege_escalation", self.risk_multiplier)
        
            if "weak_password_attack" not in self.behavior_patterns:
                self.behavior_patterns.append("weak_password_attack")
                self.threat_accum.update("weak_password_attack", self.risk_multiplier)
                # Correlation: Suspicious HTTP activity increases risk for SSH
                self.risk_multiplier += 0.5

    # Old calculate_risk_score removed in favor of ThreatAccumulator
    def get_threat_score(self) -> float:
        return self.threat_accum.score


class ThreatAccumulator:
    """
    Simplified threat scoring system.
    Uses accumulated weighted scores + time decay instead of complex Bayesian inference.
    """
    def __init__(self):
        self.score = 0.0
        self.weights = {
            "reconnaissance": 5.0,
            "lateral_movement": 15.0,
            "persistence": 20.0,
            "data_exfiltration": 25.0,
            "privilege_escalation": 30.0,
            "weak_password_attack": 10.0
        }
        self.last_update = datetime.utcnow()
        self.decay_rate = 0.5  # Points per minute decay

    def update(self, event: str, multiplier: float = 1.0):
        """Add weighted score for an event"""
        self._apply_decay()
        base_points = self.weights.get(event, 2.0)
        self.score += base_points * multiplier
        self.last_update = datetime.utcnow()

    def _apply_decay(self):
        """Apply time-based linear decay"""
        now = datetime.utcnow()
        minutes_passed = (now - self.last_update).total_seconds() / 60.0
        if minutes_passed > 0:
            decay_amount = minutes_passed * self.decay_rate
            self.score = max(0.0, self.score - decay_amount)
            self.last_update = now

    def get_risk_level(self) -> Tuple[str, float]:
        """Return qualitative risk level and raw score"""
        self._apply_decay()
        if self.score > 80: return ("Critical", self.score)
        if self.score > 50: return ("High", self.score)
        if self.score > 20: return ("Elevated", self.score)
        return ("Low", self.score)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score, 
            "last_update": self.last_update.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThreatAccumulator':
        acc = cls()
        acc.score = data.get("score", 0.0)
        if "last_update" in data:
            acc.last_update = datetime.fromisoformat(data["last_update"])
        return acc



class PredictionResult:
    """Lightweight container for Markov predictions"""

    def __init__(self, predicted: Optional[str], confidence: float, order_used: int, distribution: Dict[str, float]):
        self.predicted = predicted
        self.confidence = confidence
        self.order_used = order_used
        self.distribution = distribution


class SymbolTable:
    """Bi-directional mapping between strings and integers for memory efficiency"""
    def __init__(self):
        self.str_to_int: Dict[str, int] = {}
        self.int_to_str: Dict[int, str] = {}
        self.next_id = 0

    def get_id(self, symbol: str) -> int:
        if symbol not in self.str_to_int:
            self.str_to_int[symbol] = self.next_id
            self.int_to_str[self.next_id] = symbol
            self.next_id += 1
        return self.str_to_int[symbol]

    def get_symbol(self, idx: int) -> Optional[str]:
        return self.int_to_str.get(idx)
    
    def __len__(self):
        return self.next_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "str_to_int": self.str_to_int,
            "next_id": self.next_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SymbolTable':
        st = cls()
        st.str_to_int = data.get("str_to_int", {})
        st.next_id = data.get("next_id", 0)
        # Rebuild reverse mapping
        st.int_to_str = {v: k for k, v in st.str_to_int.items()}
        return st


class PSTNode:
    """Node in the Probabilistic Suffix Tree"""
    def __init__(self):
        self.counts: Dict[int, int] = defaultdict(int)  # Next symbol counts
        self.total_count: int = 0
        self.children: Dict[int, PSTNode] = {}  # Suffix links (reverse direction)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counts": dict(self.counts), # Convert defaultdict to dict
            "total_count": self.total_count,
            "children": {str(k): v.to_dict() for k, v in self.children.items()} # Keys must be strings for JSON
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PSTNode':
        node = cls()
        node.counts = defaultdict(int, {int(k): v for k, v in data.get("counts", {}).items()})
        node.total_count = data.get("total_count", 0)
        
        children_data = data.get("children", {})
        for k, v in children_data.items():
            node.children[int(k)] = cls.from_dict(v)
            
        return node


class MarkovPredictor:
    """
    Variable-order Markov chain implemented via Probabilistic Suffix Tree 
    with Kneser-Ney smoothing (Absolute Discounting) and integer mapping.
    """

    def __init__(self, max_order: int = 3, smoothing: float = 0.5):
        self.max_order = max_order
        self.discount = smoothing  # 'd' parameter for absolute discounting
        self.root = PSTNode()
        self.symbol_table = SymbolTable()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_order": self.max_order,
            "discount": self.discount,
            "symbol_table": self.symbol_table.to_dict(),
            "root": self.root.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarkovPredictor':
        predictor = cls(
            max_order=data.get("max_order", 3),
            smoothing=data.get("discount", 0.5)
        )
        predictor.symbol_table = SymbolTable.from_dict(data.get("symbol_table", {}))
        predictor.root = PSTNode.from_dict(data.get("root", {}))
        return predictor

    def _sanitize_input(self, sequence: List[str]) -> List[str]:
        """Sanitize input sequence: strip non-printables and limit length"""
        sanitized = []
        for token in sequence:
            # Limit token length to prevent memory DoS
            if len(token) > 256:
                token = token[:256]
            # Remove non-printable characters (keep basic ASCII + common SAFE chars)
            # This is a basic filter; for production, use a strict whitelist or regex
            clean_token = "".join(c for c in token if c.isprintable())
            if clean_token:
                sanitized.append(clean_token)
        return sanitized

    def learn_sequence(self, sequence: List[str]) -> None:
        """Ingest a sequence of commands to update counts"""
        if not sequence:
            return
            
        # SANITIZATION (Safety Net)
        sequence = self._sanitize_input(sequence)
        if not sequence:
            return

        # Convert to integers
        int_seq = [self.symbol_table.get_id(s) for s in sequence]
        n = len(int_seq)
        
        for i in range(n):
            target = int_seq[i]
            # Learn empty context (order 0) - Root updates
            self._update_node(self.root, target)
            
            # Learn higher orders
            curr_node = self.root
            # We look back up to max_order for context: sequence[i-1], sequence[i-2]...
            for j in range(1, self.max_order + 1):
                if i - j < 0:
                    break
                
                ctx_symbol = int_seq[i - j]
                if ctx_symbol not in curr_node.children:
                    curr_node.children[ctx_symbol] = PSTNode()
                curr_node = curr_node.children[ctx_symbol]
                
                self._update_node(curr_node, target)

    def _update_node(self, node: PSTNode, target_symbol: int):
        node.counts[target_symbol] += 1
        node.total_count += 1

    def prune(self, min_count: int = 2):
        """
        Prune low-frequency nodes to manage memory usage.
        Removes children with total_count < min_count.
        """
        self._prune_recursive(self.root, min_count)

    def _prune_recursive(self, node: PSTNode, min_count: int):
        # Identify children to remove
        to_remove = []
        for sym, child in node.children.items():
            if child.total_count < min_count:
                to_remove.append(sym)
            else:
                # Recurse if kept
                self._prune_recursive(child, min_count)
        
        # Remove them
        for sym in to_remove:
            del node.children[sym]

    def predict_next(self, history: List[str], whitelist: Optional[Set[str]] = None) -> PredictionResult:
        """
        Predict next command using Kneser-Ney recursiveness.
        If whitelist is provided, only consider candidates in the whitelist.
        """
        # SANITIZATION (Safety Net)
        history = self._sanitize_input(history)
        
        if not history:
             return PredictionResult(None, 0.0, 0, {})
        
        # Convert history to integers, skipping unknown symbols cautiously?
        # If the immediate context is unknown, we have no context match.
        int_history = []
        for s in history:
            if s in self.symbol_table.str_to_int:
                int_history.append(self.symbol_table.str_to_int[s])
            else:
                # If we encounter an unknown symbol, effective context breaks here?
                # For PST, treating unknown as a gap is reasonable or we treat as OOV.
                # Here we simply stop collecting context if we hit OOV.
                # Actually, better to just consider OOV as a symbol that has no children.
                # But since it's not in the table, we can't represent it yet.
                pass
        
        # 1. Identify context path in the PST
        # Traverse backwards from end of history: s_last, s_last-1 ...
        path_nodes = [self.root]
        curr = self.root
        order_used = 0
        
        rev_history = list(reversed(int_history))
        for k in range(min(len(rev_history), self.max_order)):
            sym = rev_history[k]
            if sym in curr.children:
                curr = curr.children[sym]
                path_nodes.append(curr)
                order_used = k + 1
            else:
                break
        
        candidates = set()
        for node in path_nodes:
            # Filter by whitelist if provided
            node_candidates = node.counts.keys()
            for cand_id in node_candidates:
                cand_str = self.symbol_table.get_symbol(cand_id)
                if whitelist is None or cand_str in whitelist:
                    candidates.add(cand_id)
            
        if not candidates:
             return PredictionResult(None, 0.0, 0, {})
        
        # If we have no context match at all (e.g. unknown symbol), 
        # we should probably fall back to unigram or return None if really strict.
        # The test expects None for unknown context.
        # Check if we were able to map ANY history.
        if not int_history and history:
             # All history symbols were unknown
             return PredictionResult(None, 0.0, 0, {})

        # 3. Compute probabilities for candidates using Recursive Interpolation
        scores = {}
        for cand in candidates:
            # We iterate from Root (Order 0) up to Deepest Node (Order K)
            # P_new = (max(c - d, 0) / T) + (d * distinct / T) * P_old
            
            # Base Case: Root (Order 0)
            # Unsmoothed MLE for root or Uniform? 
            # Classic KN usually has base distribution. Let's start with Root MLE.
            root_node = path_nodes[0]
            cnt = root_node.counts.get(cand, 0)
            total = root_node.total_count
            
            if total == 0:
                current_prob = 0.0
            else:
                current_prob = cnt / total
            
            # Recursive steps
            for i in range(1, len(path_nodes)):
                node = path_nodes[i]
                cnt = node.counts.get(cand, 0)
                tot = node.total_count
                
                if tot == 0: continue
                    
                distinct_succ = len(node.counts) # Number of distinct symbols following this context
                
                # alpha = max(c(w) - d, 0) / tot
                term1 = max(cnt - self.discount, 0) / tot
                
                # gamma = (d * distinct_succ) / tot
                gamma = (self.discount * distinct_succ) / tot
                
                current_prob = term1 + gamma * current_prob
                
            scores[cand] = current_prob
            
        # 4. Select best candidate
        if not scores:
            return PredictionResult(None, 0.0, 0, {})
            
        best_cand_id = max(scores.items(), key=lambda x: x[1])[0]
        best_cand_str = self.symbol_table.get_symbol(best_cand_id)
        confidence = scores[best_cand_id]
        
        distribution = {
            self.symbol_table.get_symbol(k): v 
            for k,v in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        }
        
        return PredictionResult(best_cand_str, confidence, order_used, distribution)

class ComplexityRouter:
    """
    Implements the Cascading Short-Circuit logic.
    Evaluates complexity at each layer to determine if we can exit early.
    """
    
    @staticmethod
    async def layer_0_filter(command: str, source_ip: str) -> Optional[str]:
        """
        Layer 0: Rust Reflex Layer - Sub-millisecond threat detection
        Returns threat info if detected, None if safe to proceed
        """
        if not RUST_AVAILABLE:
            return None
        
        try:
            # rust_protocol.detect_threats now returns a Dict or None
            threat_data = rust_protocol.detect_threats(command, source_ip)
            
            if threat_data:
                # Direct dictionary access (no more json.loads)
                if threat_data.get("threat_detected", False):
                    severity = threat_data.get("severity", "low")
                    
                    # Block critical threats immediately
                    if severity == "critical":
                        return f"[BLOCKED] Critical threat detected: {threat_data.get('event_type', 'unknown')}"
                    
                    # For other threats, let them through for honeypot engagement
                    logger.info(f"Layer 0 threat detected but allowing for engagement: {threat_data.get('event_type', 'unknown')}")
                
                # We can also check for 'is_noise' if needed in future
                if threat_data.get("is_noise", False):
                     logger.info("Layer 0: Identified as probable noise/scanner.")
            
            return None  # Safe to proceed to Layer 1
            
        except Exception as e:
            logger.error(f"Layer 0 threat detection failed: {e}")
            return None  # Fail open
    
    @staticmethod
    def check_l1_exit(command: str, session_history: List[str], prediction: Optional[PredictionResult] = None, confidence_threshold: float = 0.6) -> bool:
        """
        Layer 1 Exit Check: Is this a standard, predictable command sequence?
        Enhanced with session history analysis.
        If True -> Route to Static Emulator
        If False -> Proceed to Layer 2
        """
        cmd_base = command.split()[0].lower()
        
        # Standard reconnaissance commands that we can handle statically
        standard_recon = ["ls", "whoami", "pwd", "id", "echo", "cat", "ps", "uname"]
        
        if cmd_base in standard_recon:
            # Check if this is part of a predictable sequence
            if len(session_history) <= 3:  # Early interaction, handle statically
                return True
            
            # Look for predictable patterns in history
            recent_commands = [cmd.split()[0].lower() for cmd in session_history[-3:]]
            
            # Common reconnaissance sequences
            recon_sequences = [
                ["whoami", "id", "pwd"],
                ["ls", "cat", "pwd"],
                ["uname", "ps", "netstat"]
            ]
            
            for sequence in recon_sequences:
                if recent_commands == sequence[:-1] and cmd_base == sequence[-1]:
                    logger.info(f"Predictable reconnaissance sequence detected: {' -> '.join(recent_commands + [cmd_base])}")
                    return True

        # Use Markov/HMM prediction when available
        if prediction and prediction.predicted:
            if prediction.predicted == cmd_base and prediction.confidence >= confidence_threshold:
                logger.info(
                    "Layer 1 Markov exit: predicted=%s confidence=%.2f order=%d",
                    prediction.predicted,
                    prediction.confidence,
                    prediction.order_used,
                )
                return True
        
        return False

    @staticmethod
    def check_l2_exit(attacker_profile: AttackerContext, classifier: Any = None, confidence_threshold: float = 0.8) -> bool:
        """
        Layer 2: Behavioral Analysis (Advisory Only)
        
        SAFEGUARD 1: Evidence Gate
        Only run inference if we have enough data (>= 5 commands).
        
        SAFEGUARD 2: Advisory Only
        Never returns True (exit/block) based solely on L2.
        Instead, it updates the AttackerContext with an advisory signal.
        """
        # SAFEGUARD 1: Evidence Gate
        if len(attacker_profile.command_history) < 5:
             return False

        classification = None
        
        if ML_AVAILABLE and classifier and classifier.is_trained:
            # Generate features (mock adaptation)
            context_dict = {
                "session_duration": (attacker_profile.last_seen - attacker_profile.first_seen).total_seconds(),
                "command_count": len(attacker_profile.command_history),
                "behavior_patterns": attacker_profile.behavior_patterns,
                "threat_level": attacker_profile.threat_level
            }
            
            features = FeatureExtractor.vectorize(context_dict)
            predictions = classifier.predict(features)
            
            # Find best class
            if predictions:
                best_class = max(predictions.items(), key=lambda x: x[1])
                classification = best_class[0]
                confidence = best_class[1]
                
                # SAFEGUARD 3: Blind Labels (Cluster_A/B)
                # Map internal clusters to human readable names for logging only
                display_name = classification
                if classification == "Cluster_A": display_name = "APT (High Stealth)"
                if classification == "Cluster_B": display_name = "Script Kiddie (Noisy)"

                logger.info(f"Layer 2 Advisory: {display_name} ({confidence:.2f})")
                
                if confidence >= confidence_threshold:
                    # ADVISORY ACTION: Boost risk score instead of blocking
                    attacker_profile.risk_multiplier += 0.5
                    logger.info("Layer 2 increased risk multiplier due to high-confidence classification.")
                    
                    # We DO NOT return True here. Layer 2 never exits/blocks alone.
                    return False
        
        return False

    @staticmethod
    def check_l3_exit(strategy_complexity: Dict[str, Any]) -> bool:
        """
        Layer 3 Exit Check: Do we need to generate a new strategy?
        If False -> Use standard strategy (Static/Template)
        If True -> Proceed to Layer 4 (Persona/LLM)
        """
        # Check if current strategy parameters are sufficient
        novelty_score = strategy_complexity.get("novelty_score", 0.0)
        engagement_quality = strategy_complexity.get("engagement_quality", 0.5)
        
        # Use LLM only for highly novel or low-engagement scenarios
        needs_generative = novelty_score > 0.7 or engagement_quality < 0.3
        
        logger.info(f"Strategy complexity check: novelty={novelty_score:.2f}, "
                   f"engagement={engagement_quality:.2f}, needs_llm={needs_generative}")
        
        return not needs_generative

import os
from ..config import get_config

class AIEngine:
    """Main AI engine for generating adaptive honeypot responses"""
    
    def __init__(self, provider: AIProvider = AIProvider.STUB, storage_path: str = "data/ai_models"):
        self.provider = provider
        self.storage_path = storage_path
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_path, exist_ok=True)
        
        self.attacker_contexts: Dict[str, AttackerContext] = {}
        self.response_templates = self._load_response_templates()
        self.personality_profiles = self._load_personality_profiles()
        
        # Layer 1: Service-Specific Intuition Models
        # Separate predictors for SSH and HTTP to prevent cross-contamination
        self.predictors: Dict[str, MarkovPredictor] = {
            "ssh": MarkovPredictor(max_order=3, smoothing=0.5),
            "http": MarkovPredictor(max_order=2, smoothing=0.5)
        }
        
        # Attempt to load persisted models
        self.load_state()
        
        # Valid commands whitelist for Hallucination Guard
        self.command_whitelist = {
            "ls", "cd", "cat", "pwd", "whoami", "id", "uname", "ps", "netstat",
            "echo", "mkdir", "rm", "touch", "mv", "cp", "grep", "find", "ssh",
            "scp", "wget", "curl", "ping", "systemctl", "service", "crontab",
            "vi", "nano", "vim", "history", "exit", "sudo", "su", "help", "clear"
        }
        
        # Layer 2: Behavioral Classifier
        self.behavioral_classifier = None
        if ML_AVAILABLE:
            self.behavioral_classifier = BehavioralClassifier()
            if not self.behavioral_classifier.is_trained:
                logger.info("Initializing Layer 2 model with mock training data...")
                self.behavioral_classifier.mock_train()
        
        # Configuration for different providers
        self.provider_configs = {
            AIProvider.STUB: {"enabled": True},
            AIProvider.OPENAI: {"api_key": None, "model": "gpt-3.5-turbo"},
            AIProvider.ANTHROPIC: {"api_key": None, "model": "claude-3-haiku"},
            AIProvider.LOCAL_LLM: {"endpoint": "http://localhost:8080", "model": "local"},
            AIProvider.OLLAMA: {"endpoint": "http://localhost:11434", "model": "llama2"}
        }
        
        logger.info(f"AI Engine initialized with provider: {provider}")
        # Deployment toggles for observation/predict-only mode
        self.deployment = get_config().deployment

    def save_state(self) -> None:
        """Persist AI models to disk"""
        try:
            for name, predictor in self.predictors.items():
                file_path = os.path.join(self.storage_path, f"{name}_markov.json")
                with open(file_path, 'w') as f:
                    json.dump(predictor.to_dict(), f)
            logger.info("AI Engine state saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save AI Engine state: {e}")

    def load_state(self) -> None:
        """Load AI models from disk"""
        try:
            for name in self.predictors.keys():
                file_path = os.path.join(self.storage_path, f"{name}_markov.json")
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        self.predictors[name] = MarkovPredictor.from_dict(data)
                    logger.info(f"Loaded {name} model from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load AI Engine state: {e}")

    def shutdown(self):
        """Explicitly save state on shutdown"""
        logger.info("AIEngine shutting down, saving state...")
        self.save_state()

    def _load_response_templates(self) -> Dict[str, List[str]]:
        """Load response templates for different scenarios"""
        return {
            "ssh_reconnaissance": [
                "Generating realistic directory listing based on attack pattern...",
                "Adapting file system to match attacker expectations...",
                "Creating believable process list for reconnaissance..."
            ],
            "login_failure": [
                "Simulating authentication delay to waste attacker time...",
                "Generating believable error message...",
                "Adapting response based on login attempt pattern..."
            ],
            "privilege_escalation": [
                "Detecting privilege escalation attempt...",
                "Simulating security controls...",
                "Generating realistic sudo response..."
            ],
            "data_exfiltration": [
                "Monitoring file access patterns...",
                "Generating believable file contents...",
                "Simulating network connectivity issues..."
            ]
        }
    
    def _load_personality_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load different system personalities for realistic responses"""
        return {
            "corporate_server": {
                "hostname_pattern": "srv-{dept}-{num:02d}",
                "user_patterns": ["admin", "service", "backup"],
                "directory_structure": "corporate",
                "security_level": "high",
                "response_style": "professional"
            },
            "home_router": {
                "hostname_pattern": "router-{random}",
                "user_patterns": ["admin", "user"],
                "directory_structure": "embedded",
                "security_level": "low",
                "response_style": "simple"
            },
            "iot_device": {
                "hostname_pattern": "cam-{location}-{id}",
                "user_patterns": ["root", "admin"],
                "directory_structure": "minimal",
                "security_level": "very_low",
                "response_style": "basic"
            },
            "development_server": {
                "hostname_pattern": "dev-{project}-{env}",
                "user_patterns": ["dev", "admin", "test"],
                "directory_structure": "development",
                "security_level": "medium",
                "response_style": "casual"
            }
        }
    
    async def generate_response(self, 
                              response_type: ResponseType, 
                              context: Dict[str, Any],
                              attacker_ip: str,
                              session_id: str) -> str:
        """Generate adaptive response based on context and attacker behavior"""
        
        # KEY CHANGE FOR CORRELATION: 
        # Context is now keyed by IP only. This links SSH and HTTP sessions together.
        context_key = attacker_ip
        if context_key not in self.attacker_contexts:
            self.attacker_contexts[context_key] = AttackerContext(attacker_ip, session_id)
        
        attacker_context = self.attacker_contexts[context_key]
        # Update latest session ID if it changed
        if attacker_context.session_id != session_id:
             attacker_context.session_id = session_id 
        
        # Update context with new activity
        if response_type == ResponseType.SSH_COMMAND:
            attacker_context.update_activity("ssh_command", context)
            command = context.get("command", "")
            session_history = context.get("session_history", [])

            # Train predictor with recent history (excluding current command if provided separately)
            # Use the SSH-specific predictor
            predictor = self.predictors["ssh"]
            
            history_for_training = attacker_context.command_history[-(predictor.max_order + 1):]
            predictor.learn_sequence(history_for_training)

            # Predict next command using history without the current command to gauge predictability
            history_for_prediction = attacker_context.command_history[:-1] if attacker_context.command_history else []
            
            # Layer 1 Hallucination Guard: Only predict valid commands
            markov_prediction = predictor.predict_next(
                history_for_prediction, 
                whitelist=self.command_whitelist
            )
            
            # MIRAGE CASCADING SHORT-CIRCUIT ARCHITECTURE
            
            # Layer 0: Rust Reflex - Threat filtering
            layer0_result = await ComplexityRouter.layer_0_filter(command, attacker_ip)
            if layer0_result:
                logger.info(f"Layer 0 exit: {layer0_result}")
                return layer0_result
            
            # Observation mode short-circuit: predict-only, do not influence
            if self.deployment.MODE == "observation" and not self.deployment.LAYER_1_INFLUENCE:
                # Update context/predictors only; return deterministic stub
                return await self._generate_stub_response(response_type, context, attacker_context)

            # Layer 1: Intuition - Predictable command sequences
            if ComplexityRouter.check_l1_exit(command, session_history, markov_prediction):
                logger.info(f"Layer 1 exit: Standard command sequence for '{command}'")
                return await self._generate_stub_response(response_type, context, attacker_context)
            
            # Layer 2: Reasoning - Known attacker profiles
            if ComplexityRouter.check_l2_exit(attacker_context, self.behavioral_classifier):
                logger.info(f"Layer 2 exit: Known profile {attacker_context.threat_level}")
                return await self._generate_stub_response(response_type, context, attacker_context)
            
            # Layer 3: Strategy - Standard vs novel strategies
            strategy_complexity = {
                "novelty_score": self._calculate_novelty_score(attacker_context, command),
                "engagement_quality": self._calculate_engagement_quality(attacker_context)
            }
            
            if ComplexityRouter.check_l3_exit(strategy_complexity):
                logger.info(f"Layer 3 exit: Standard strategy sufficient")
                return await self._generate_stub_response(response_type, context, attacker_context)
            
            # Layer 4: Persona - LLM-based generative response
            # In engagement mode only, escalate to LLM; otherwise keep stub
            if self.deployment.MODE == "engagement":
                logger.info(f"Layer 4: Generative LLM response needed for novel interaction")
                return await self._generate_llm_response(response_type, context, attacker_context)
            return await self._generate_stub_response(response_type, context, attacker_context)
            
        elif response_type == ResponseType.HTTP_LOGIN:
            attacker_context.update_activity("login_attempt", context)
            # Apply similar cascading logic for HTTP
            return await self._generate_stub_response(response_type, context, attacker_context)
        
        # Generate response based on provider
        if self.provider == AIProvider.STUB:
            return await self._generate_stub_response(response_type, context, attacker_context)
        else:
            return await self._generate_llm_response(response_type, context, attacker_context)
    
    async def _generate_stub_response(self, 
                                    response_type: ResponseType, 
                                    context: Dict[str, Any],
                                    attacker_context: AttackerContext) -> str:
        """Generate stub responses for development and testing"""
        
        base_responses = {
            ResponseType.SSH_COMMAND: self._generate_ssh_stub_response,
            ResponseType.HTTP_LOGIN: self._generate_http_stub_response,
            ResponseType.SYSTEM_ERROR: self._generate_error_stub_response,
            ResponseType.SOCIAL_ENGINEERING: self._generate_social_stub_response,
            ResponseType.THREAT_ASSESSMENT: self._generate_threat_stub_response
        }
        
        generator = base_responses.get(response_type, self._generate_default_stub_response)
        return await generator(context, attacker_context)
    
    async def _generate_ssh_stub_response(self, context: Dict[str, Any], attacker_context: AttackerContext) -> str:
        """Generate SSH command stub responses"""
        command = context.get("command", "").lower()
        
        # Adapt response based on attacker behavior patterns
        if "reconnaissance" in attacker_context.behavior_patterns:
            recon_responses = [
                f"[AI-Adaptive] Enhanced directory listing for reconnaissance pattern",
                f"[AI-Adaptive] Detailed process information for {command}",
                f"[AI-Adaptive] Network configuration adapted to attacker interest"
            ]
            return random.choice(recon_responses)
        
        elif "lateral_movement" in attacker_context.behavior_patterns:
            lateral_responses = [
                f"[AI-Adaptive] Simulating network connectivity for {command}",
                f"[AI-Adaptive] Generating believable SSH connection errors",
                f"[AI-Adaptive] Adapting network topology for lateral movement"
            ]
            return random.choice(lateral_responses)
        
        else:
            return f"[AI-Stub] Adaptive response for SSH command: {command}"
    
    async def _generate_http_stub_response(self, context: Dict[str, Any], attacker_context: AttackerContext) -> str:
        """Generate HTTP login stub responses"""
        username = context.get("username", "")
        
        if "weak_password_attack" in attacker_context.behavior_patterns:
            return f"[AI-Adaptive] Detected brute force pattern, implementing delay tactics"
        elif "privilege_escalation" in attacker_context.behavior_patterns:
            return f"[AI-Adaptive] Admin account access attempt detected, enhancing deception"
        else:
            return f"[AI-Stub] Adaptive login response for user: {username}"
    
    async def _generate_error_stub_response(self, context: Dict[str, Any], attacker_context: AttackerContext) -> str:
        """Generate system error stub responses"""
        return f"[AI-Stub] Adaptive error message based on {len(attacker_context.behavior_patterns)} behavior patterns"
    
    async def _generate_social_stub_response(self, context: Dict[str, Any], attacker_context: AttackerContext) -> str:
        """Generate social engineering response stubs"""
        return f"[AI-Stub] Social engineering response adapted to attacker profile"
    
    async def _generate_threat_stub_response(self, context: Dict[str, Any], attacker_context: AttackerContext) -> str:
        """Generate threat assessment stub responses"""
        threat_score = len(attacker_context.behavior_patterns) * 10
        return f"[AI-Stub] Threat assessment: {threat_score}% based on {attacker_context.behavior_patterns}"
    
    async def _generate_default_stub_response(self, context: Dict[str, Any], attacker_context: AttackerContext) -> str:
        """Generate default stub response"""
        return f"[AI-Stub] Default adaptive response for {attacker_context.ip}"
    
    async def _generate_llm_response(self, 
                                   response_type: ResponseType, 
                                   context: Dict[str, Any],
                                   attacker_context: AttackerContext) -> str:
        """Generate responses using actual LLM providers (placeholder for future implementation)"""
        # This would integrate with actual LLM APIs
        # For now, return enhanced stub response
        return f"[LLM-Ready] {self.provider} integration point for {response_type}"
    
    async def analyze_attacker_behavior(self, attacker_ip: str, session_id: str) -> Dict[str, Any]:
        """Analyze and return attacker behavior summary"""
        context_key = f"{attacker_ip}_{session_id}"
        
        if context_key not in self.attacker_contexts:
            return {"error": "No context found for attacker"}
        
        attacker_context = self.attacker_contexts[context_key]
        
        return {
            "ip": attacker_context.ip,
            "session_id": attacker_context.session_id,
            "session_duration": (attacker_context.last_seen - attacker_context.first_seen).total_seconds(),
            "command_count": len(attacker_context.command_history),
            "login_attempts": len(attacker_context.login_attempts),
            "behavior_patterns": attacker_context.behavior_patterns,
            "threat_level": attacker_context.threat_level,
            "tools_detected": attacker_context.tools_detected,
            "latest_commands": attacker_context.command_history[-5:] if attacker_context.command_history else [],
            "assessment": self._generate_behavior_assessment(attacker_context)
        }
    
    def _generate_behavior_assessment(self, attacker_context: AttackerContext) -> str:
        """Generate human-readable behavior assessment"""
        if not attacker_context.behavior_patterns:
            return "Initial reconnaissance phase, low threat level"
        
        if len(attacker_context.behavior_patterns) >= 3:
            return "Advanced persistent threat detected, high engagement recommended"
        elif "lateral_movement" in attacker_context.behavior_patterns:
            return "Active lateral movement detected, medium-high threat level"
        elif "reconnaissance" in attacker_context.behavior_patterns:
            return "Standard reconnaissance phase, monitoring recommended"
        else:
            return "Basic probing detected, low-medium threat level"
    
    async def get_adaptive_personality(self, context: Dict[str, Any]) -> str:
        """Select appropriate system personality based on context"""
        # Simple personality selection logic (can be enhanced with ML)
        if "admin" in context.get("username", "").lower():
            return "corporate_server"
        elif "router" in context.get("user_agent", "").lower():
            return "home_router"
        elif "cam" in context.get("path", "").lower():
            return "iot_device"
        else:
            return "development_server"
    
    def _calculate_novelty_score(self, attacker_context: AttackerContext, command: str) -> float:
        """Calculate how novel/unusual this command is for this attacker"""
        cmd_base = command.split()[0].lower()
        
        # Check if this is a new command for this attacker
        previous_commands = [cmd.split()[0].lower() for cmd in attacker_context.command_history[:-1]]
        
        if cmd_base not in previous_commands:
            novelty_base = 0.6  # New command gets base novelty
        else:
            novelty_base = 0.2  # Repeated command
        
        # Increase novelty for complex commands
        complex_commands = ["find", "grep", "awk", "sed", "python", "perl", "wget", "curl", "nc"]
        if cmd_base in complex_commands:
            novelty_base += 0.3
        
        # Increase novelty for commands with many arguments
        arg_count = len(command.split()) - 1
        if arg_count > 3:
            novelty_base += 0.2
        
        return min(novelty_base, 1.0)
    
    def _calculate_engagement_quality(self, attacker_context: AttackerContext) -> float:
        """Calculate how well we're engaging with this attacker"""
        if len(attacker_context.command_history) == 0:
            return 0.5  # Neutral for new sessions
        
        # Base engagement on session duration and activity
        session_duration_minutes = (attacker_context.last_seen - attacker_context.first_seen).total_seconds() / 60
        command_rate = len(attacker_context.command_history) / max(session_duration_minutes, 1)
        
        # Good engagement: 1-5 commands per minute
        if 1 <= command_rate <= 5:
            engagement_base = 0.7
        elif command_rate > 5:
            engagement_base = 0.4  # Too fast, might be automated
        else:
            engagement_base = 0.3  # Too slow, might be losing interest
        
        # Bonus for diverse behavior patterns
        pattern_diversity = len(set(attacker_context.behavior_patterns))
        engagement_base += pattern_diversity * 0.1
        
        return min(engagement_base, 1.0)
