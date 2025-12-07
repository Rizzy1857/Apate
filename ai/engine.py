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
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum

# Import Rust protocol for Layer 0 threat detection
try:
    import rust_protocol
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.warning("Rust protocol library not available - Layer 0 disabled")

logger = logging.getLogger(__name__)

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
        elif command.split()[0].lower() in lateral_movement:
            if "lateral_movement" not in self.behavior_patterns:
                self.behavior_patterns.append("lateral_movement")
        elif command.split()[0].lower() in persistence:
            if "persistence" not in self.behavior_patterns:
                self.behavior_patterns.append("persistence")
        elif command.split()[0].lower() in data_exfiltration:
            if "data_exfiltration" not in self.behavior_patterns:
                self.behavior_patterns.append("data_exfiltration")
    
    def _analyze_login_patterns(self, login_data: Dict[str, Any]):
        """Analyze login patterns for threat assessment"""
        username = login_data.get("username", "").lower()
        password = login_data.get("password", "").lower()
        
        # Check for common attack patterns
        if username in ["admin", "administrator", "root"]:
            if "privilege_escalation" not in self.behavior_patterns:
                self.behavior_patterns.append("privilege_escalation")
        
            if "weak_password_attack" not in self.behavior_patterns:
                self.behavior_patterns.append("weak_password_attack")


class PredictionResult:
    """Lightweight container for Markov predictions"""

    def __init__(self, predicted: Optional[str], confidence: float, order_used: int, distribution: Dict[str, float]):
        self.predicted = predicted
        self.confidence = confidence
        self.order_used = order_used
        self.distribution = distribution


class MarkovPredictor:
    """Variable-order Markov chain with simple additive smoothing"""

    def __init__(self, max_order: int = 3, smoothing: float = 0.5):
        self.max_order = max_order
        self.smoothing = smoothing
        # counts[order][context_tuple][next_token] = count
        self.counts: Dict[int, Dict[Tuple[str, ...], Dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    def learn_sequence(self, sequence: List[str]) -> None:
        """Ingest a sequence of commands to update counts"""
        if not sequence:
            return
        n = len(sequence)
        for idx in range(n):
            next_token = sequence[idx]
            # Build contexts up to max_order
            for order in range(1, self.max_order + 1):
                if idx - order < 0:
                    continue
                context = tuple(sequence[idx - order: idx])
                self.counts[order][context][next_token] += 1

    def predict_next(self, history: List[str]) -> PredictionResult:
        """Predict next command given a history. Falls back from max_order to 1."""
        if not history:
            return PredictionResult(None, 0.0, 0, {})

        for order in range(min(self.max_order, len(history)), 0, -1):
            context = tuple(history[-order:])
            next_counts = self.counts[order].get(context)
            if not next_counts:
                continue
            total = sum(next_counts.values())
            if total == 0:
                continue

            # Apply simple additive smoothing
            vocab_size = len(next_counts)
            smoothed = {token: (count + self.smoothing) / (total + self.smoothing * vocab_size) for token, count in next_counts.items()}
            predicted = max(smoothed.items(), key=lambda kv: kv[1])
            confidence = predicted[1]
            distribution = dict(sorted(smoothed.items(), key=lambda kv: kv[1], reverse=True))
            return PredictionResult(predicted[0], confidence, order, distribution)

        return PredictionResult(None, 0.0, 0, {})

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
            threat_json = rust_protocol.detect_threats(command, source_ip)
            if threat_json:
                # Parse threat and decide if we should block or engage
                threat_data = json.loads(threat_json)
                severity = threat_data.get("severity", "low")
                
                # Block critical threats immediately
                if severity == "critical":
                    return f"[BLOCKED] Critical threat detected: {threat_data.get('event_type', 'unknown')}"
                
                # For other threats, let them through for honeypot engagement
                logger.info(f"Layer 0 threat detected but allowing for engagement: {threat_data.get('event_type', 'unknown')}")
            
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
    def check_l2_exit(attacker_profile: AttackerContext, confidence_threshold: float = 0.8) -> bool:
        """
        Layer 2 Exit Check: Is this a known attacker profile with a cached strategy?
        Enhanced with confidence scoring.
        If True -> Route to Static Emulator (with cached strategy)
        If False -> Proceed to Layer 3
        """
        # Calculate confidence based on behavior consistency
        if len(attacker_profile.behavior_patterns) == 0:
            return False
        
        # Simple confidence calculation based on pattern consistency
        pattern_confidence = min(len(attacker_profile.behavior_patterns) / 3.0, 1.0)
        
        # Check if we have a strong classification
        known_profiles = ["script_kiddie", "automated_scanner", "persistence_seeker", "data_harvester"]
        
        if (attacker_profile.threat_level in known_profiles and 
            pattern_confidence >= confidence_threshold):
            logger.info(f"High-confidence profile match: {attacker_profile.threat_level} ({pattern_confidence:.2f})")
            return True
        
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

class AIEngine:
    """Main AI engine for generating adaptive honeypot responses"""
    
    def __init__(self, provider: AIProvider = AIProvider.STUB):
        self.provider = provider
        self.attacker_contexts: Dict[str, AttackerContext] = {}
        self.response_templates = self._load_response_templates()
        self.personality_profiles = self._load_personality_profiles()
        self.markov_predictor = MarkovPredictor(max_order=3, smoothing=0.5)
        
        # Configuration for different providers
        self.provider_configs = {
            AIProvider.STUB: {"enabled": True},
            AIProvider.OPENAI: {"api_key": None, "model": "gpt-3.5-turbo"},
            AIProvider.ANTHROPIC: {"api_key": None, "model": "claude-3-haiku"},
            AIProvider.LOCAL_LLM: {"endpoint": "http://localhost:8080", "model": "local"},
            AIProvider.OLLAMA: {"endpoint": "http://localhost:11434", "model": "llama2"}
        }
        
        logger.info(f"AI Engine initialized with provider: {provider}")
    
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
        
        # Get or create attacker context
        context_key = f"{attacker_ip}_{session_id}"
        if context_key not in self.attacker_contexts:
            self.attacker_contexts[context_key] = AttackerContext(attacker_ip, session_id)
        
        attacker_context = self.attacker_contexts[context_key]
        
        # Update context with new activity
        if response_type == ResponseType.SSH_COMMAND:
            attacker_context.update_activity("ssh_command", context)
            command = context.get("command", "")
            session_history = context.get("session_history", [])

            # Train predictor with recent history (excluding current command if provided separately)
            history_for_training = attacker_context.command_history[-(self.markov_predictor.max_order + 1):]
            self.markov_predictor.learn_sequence(history_for_training)

            # Predict next command using history without the current command to gauge predictability
            history_for_prediction = attacker_context.command_history[:-1] if attacker_context.command_history else []
            markov_prediction = self.markov_predictor.predict_next(history_for_prediction)
            
            # MIRAGE CASCADING SHORT-CIRCUIT ARCHITECTURE
            
            # Layer 0: Rust Reflex - Threat filtering
            layer0_result = await ComplexityRouter.layer_0_filter(command, attacker_ip)
            if layer0_result:
                logger.info(f"Layer 0 exit: {layer0_result}")
                return layer0_result
            
            # Layer 1: Intuition - Predictable command sequences
            if ComplexityRouter.check_l1_exit(command, session_history, markov_prediction):
                logger.info(f"Layer 1 exit: Standard command sequence for '{command}'")
                return await self._generate_stub_response(response_type, context, attacker_context)
            
            # Layer 2: Reasoning - Known attacker profiles
            if ComplexityRouter.check_l2_exit(attacker_context):
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
            logger.info(f"Layer 4: Generative LLM response needed for novel interaction")
            return await self._generate_llm_response(response_type, context, attacker_context)
            
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
