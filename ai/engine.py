"""
AI Engine - Foundation Layer
----------------------------
This is the foundation AI engine that will be superseded by the Mirage
five-layer cognitive architecture. Currently provides basic stubbed responses
and will serve as the base for Layer 4 (Persona Layer) implementation.

The new architecture will include:
- Layer 0: Rust reflex layer (sub-millisecond deterministic responses)
- Layer 1: Intuition layer (HMM command prediction)
- Layer 2: Reasoning layer (ML behavioral classification)
- Layer 3: Strategy layer (RL optimization)
- Layer 4: Persona layer (LLM-based responses) - evolution of this module

This engine provides the foundation and will be integrated into the cognitive
director when the full Mirage architecture is implemented.
"""

import asyncio
import logging
import random
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum

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
        
        if password in ["password", "123456", "admin", "root"]:
            if "weak_password_attack" not in self.behavior_patterns:
                self.behavior_patterns.append("weak_password_attack")

class AIEngine:
    """Main AI engine for generating adaptive honeypot responses"""
    
    def __init__(self, provider: AIProvider = AIProvider.STUB):
        self.provider = provider
        self.attacker_contexts: Dict[str, AttackerContext] = {}
        self.response_templates = self._load_response_templates()
        self.personality_profiles = self._load_personality_profiles()
        
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
        elif response_type == ResponseType.HTTP_LOGIN:
            attacker_context.update_activity("login_attempt", context)
        
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
