"""
Monitoring and Metrics Module
----------------------------
Provides MTTD (Mean Time To Discovery) tracking and other security metrics
for validating the effectiveness of the Mirage cognitive layers.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class SessionMetrics:
    """Track metrics for a honeypot session"""
    session_id: str
    source_ip: str
    start_time: datetime
    end_time: Optional[datetime] = None
    discovery_time: Optional[datetime] = None
    interaction_count: int = 0
    commands_executed: int = 0
    login_attempts: int = 0
    honeypots_triggered: int = 0
    threat_score: float = 0.0
    discovered: bool = False
    
    @property
    def session_duration(self) -> float:
        """Session duration in seconds"""
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()
    
    @property
    def time_to_discovery(self) -> Optional[float]:
        """Time to discovery in seconds, if discovered"""
        if self.discovery_time:
            return (self.discovery_time - self.start_time).total_seconds()
        return None

class MTTDTracker:
    """Tracks Mean Time To Discovery metrics for honeypot effectiveness"""
    
    def __init__(self):
        # Prometheus metrics
        self.registry = CollectorRegistry()
        
        self.sessions_total = Counter(
            'honeypot_sessions_total',
            'Total number of honeypot sessions',
            ['source_type', 'protocol'],
            registry=self.registry
        )
        
        self.session_duration = Histogram(
            'honeypot_session_duration_seconds',
            'Duration of honeypot sessions',
            ['protocol', 'discovered'],
            registry=self.registry
        )
        
        self.discovery_time = Histogram(
            'honeypot_discovery_time_seconds', 
            'Time until honeypot discovery',
            ['protocol', 'layer_active'],
            buckets=[10, 30, 60, 120, 300, 600, 1200, 1800, 3600],  # 10s to 1h
            registry=self.registry
        )
        
        self.current_mttd = Gauge(
            'honeypot_current_mttd_seconds',
            'Current calculated MTTD',
            ['protocol', 'time_window'],
            registry=self.registry
        )
        
        self.active_sessions = Gauge(
            'honeypot_active_sessions',
            'Number of active honeypot sessions',
            registry=self.registry
        )
        
        # Session tracking
        self.sessions: Dict[str, SessionMetrics] = {}
        self.completed_sessions: List[SessionMetrics] = []
        
        # Discovery detection patterns
        self.discovery_patterns = {
            "rapid_exit": {"max_duration": 5, "min_commands": 1},
            "error_sequence": {"error_threshold": 3, "time_window": 30},
            "fingerprinting": {"fingerprint_commands": ["uname", "whoami", "id", "ps"], "threshold": 3},
            "honeypot_keywords": ["honey", "pot", "fake", "deception", "trap"]
        }
    
    async def start_session(self, session_id: str, source_ip: str, protocol: str = "unknown") -> SessionMetrics:
        """Start tracking a new session"""
        session = SessionMetrics(
            session_id=session_id,
            source_ip=source_ip,
            start_time=datetime.utcnow()
        )
        
        self.sessions[session_id] = session
        self.sessions_total.labels(source_type="external", protocol=protocol).inc()
        self.active_sessions.set(len(self.sessions))
        
        logger.info(f"Started tracking session {session_id} from {source_ip}")
        return session
    
    async def record_interaction(self, session_id: str, interaction_type: str, 
                               command: Optional[str] = None, success: bool = True):
        """Record an interaction and check for discovery patterns"""
        if session_id not in self.sessions:
            logger.warning(f"Interaction recorded for unknown session {session_id}")
            return
        
        session = self.sessions[session_id]
        session.interaction_count += 1
        
        if interaction_type == "ssh_command":
            session.commands_executed += 1
        elif interaction_type == "login_attempt":
            session.login_attempts += 1
        elif interaction_type == "honeytoken_triggered":
            session.honeypots_triggered += 1
        
        # Check for discovery patterns
        await self._check_discovery_patterns(session_id, interaction_type, command, success)
    
    async def _check_discovery_patterns(self, session_id: str, interaction_type: str, 
                                      command: Optional[str], success: bool):
        """Analyze interaction patterns to detect if honeypot was discovered"""
        session = self.sessions[session_id]
        
        # Pattern 1: Rapid exit after minimal interaction
        if (session.session_duration < self.discovery_patterns["rapid_exit"]["max_duration"] and 
            session.commands_executed >= self.discovery_patterns["rapid_exit"]["min_commands"]):
            await self._mark_discovered(session_id, "rapid_exit")
            return
        
        # Pattern 2: Honeypot-related keywords in commands
        if command:
            command_lower = command.lower()
            for keyword in self.discovery_patterns["honeypot_keywords"]:
                if keyword in command_lower:
                    await self._mark_discovered(session_id, "honeypot_keywords")
                    return
        
        # Pattern 3: Fingerprinting behavior (multiple system info commands)
        if command and interaction_type == "ssh_command":
            cmd_base = command.split()[0].lower()
            if cmd_base in self.discovery_patterns["fingerprinting"]["fingerprint_commands"]:
                # Count recent fingerprinting commands
                # This is a simplified check - could be enhanced with time windows
                if session.commands_executed >= self.discovery_patterns["fingerprinting"]["threshold"]:
                    session.threat_score += 0.2
                    if session.threat_score >= 0.8:  # High confidence threshold
                        await self._mark_discovered(session_id, "fingerprinting_behavior")
    
    async def _mark_discovered(self, session_id: str, reason: str):
        """Mark a session as discovered"""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        if not session.discovered:
            session.discovered = True
            session.discovery_time = datetime.utcnow()
            
            # Record discovery metrics
            discovery_time_sec = session.time_to_discovery
            if discovery_time_sec:
                self.discovery_time.labels(
                    protocol="ssh",  # Could be made dynamic
                    layer_active="layer0"  # Will be dynamic based on active layers
                ).observe(discovery_time_sec)
            
            logger.info(f"Session {session_id} discovered after {discovery_time_sec:.1f}s - Reason: {reason}")
    
    async def end_session(self, session_id: str, reason: str = "normal_exit"):
        """End session tracking"""
        if session_id not in self.sessions:
            logger.warning(f"Attempted to end unknown session {session_id}")
            return
        
        session = self.sessions[session_id]
        session.end_time = datetime.utcnow()
        
        # Record session duration
        self.session_duration.labels(
            protocol="ssh",  # Could be dynamic
            discovered=str(session.discovered).lower()
        ).observe(session.session_duration)
        
        # Move to completed sessions
        self.completed_sessions.append(session)
        del self.sessions[session_id]
        self.active_sessions.set(len(self.sessions))
        
        logger.info(f"Ended session {session_id}, Duration: {session.session_duration:.1f}s, "
                   f"Discovered: {session.discovered}")
    
    def calculate_mttd(self, time_window_hours: int = 24, protocol: str = "all") -> Dict[str, float]:
        """Calculate MTTD for discovered sessions within time window"""
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        recent_sessions = [
            s for s in self.completed_sessions 
            if s.start_time >= cutoff_time and s.discovered and s.time_to_discovery
        ]
        
        if not recent_sessions:
            return {
                "mttd_mean": 0.0,
                "mttd_median": 0.0,
                "sample_size": 0,
                "discovery_rate": 0.0
            }
        
        discovery_times = [s.time_to_discovery for s in recent_sessions if s.time_to_discovery]
        total_sessions = len([s for s in self.completed_sessions if s.start_time >= cutoff_time])
        
        discovery_times.sort()
        
        mttd_mean = sum(discovery_times) / len(discovery_times)
        mttd_median = discovery_times[len(discovery_times) // 2] if discovery_times else 0.0
        discovery_rate = len(recent_sessions) / max(total_sessions, 1)
        
        # Update Prometheus gauge
        self.current_mttd.labels(protocol=protocol, time_window=f"{time_window_hours}h").set(mttd_mean)
        
        return {
            "mttd_mean": mttd_mean,
            "mttd_median": mttd_median,
            "sample_size": len(recent_sessions),
            "discovery_rate": discovery_rate,
            "total_sessions": total_sessions
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        return {
            "active_sessions": len(self.sessions),
            "total_completed": len(self.completed_sessions),
            "mttd_24h": self.calculate_mttd(24),
            "mttd_7d": self.calculate_mttd(24 * 7),
            "current_sessions": [
                {
                    "session_id": s.session_id,
                    "source_ip": s.source_ip,
                    "duration": s.session_duration,
                    "interactions": s.interaction_count,
                    "threat_score": s.threat_score
                }
                for s in self.sessions.values()
            ]
        }
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        from prometheus_client import generate_latest
        return generate_latest(self.registry).decode('utf-8')

# Global instance
mttd_tracker = MTTDTracker()
