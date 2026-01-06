"""
Household Failure Mode Engineering
===================================

DESIGN PRINCIPLE: If Apate breaks, the network must not break.

STATUS: DORMANT GUARDRAIL (not active in hot path)

This module DEFINES safety invariants but is NOT integrated into core logic yet.

When active (Q2 2026+):
- Ensures graceful degradation under failure
- Enforces memory-bounded operations (no OOM)
- Provides timeout protection (no hangs)
- Maintains network transparency (observer, not blocker)

Until Q2 2026:
- Exists as a contract/spec
- Used in tests and validation
- Wraps deployment but doesn't intervene
"""

import asyncio
import logging
try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    psutil = None  # Fallback when psutil isn't available
    _HAS_PSUTIL = False
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class DegradationLevel(str, Enum):
    """System degradation states"""
    NORMAL = "normal"              # Full AI capability
    SAFE_MODE = "safe_mode"        # Reduced layers, no ML
    OBSERVER_ONLY = "observer_only"  # Read-only, no actions
    OFFLINE = "offline"            # Complete failure, network passes through


@dataclass
class SystemBudgets:
    """Hard limits to prevent resource exhaustion"""
    
    # Memory
    max_memory_percent: float = 80.0  # Max CPU memory usage
    max_ai_memory_mb: int = 200       # Max for AI models
    
    # CPU
    max_cpu_percent: float = 75.0     # Max CPU usage
    max_cpu_duration_seconds: int = 5  # Max processing time per request
    
    # Network
    max_network_latency_ms: int = 200  # Max processing latency
    default_timeout_seconds: float = 5.0  # Default timeout for any operation
    
    # Graceful degradation thresholds
    degrade_at_memory_percent: float = 70.0
    degrade_at_cpu_percent: float = 60.0


class SafetyBoundedPredictor:
    """
    Markov predictor with hard memory limits.
    
    If memory exceeded, gracefully prune oldest data instead of crashing.
    """
    
    def __init__(self, 
                 max_memory_mb: int = 50,
                 max_sessions: int = 100):
        """
        Initialize bounded predictor.
        
        Args:
            max_memory_mb: Hard memory cap
            max_sessions: Max number of active attacker sessions to track
        """
        self.max_memory = max_memory_mb * 1024 * 1024  # Convert to bytes
        self.max_sessions = max_sessions
        self.current_size = 0
        
        # Session management
        self.sessions = {}  # Tracked sessions
        self.session_timestamps = {}  # For LRU eviction
        
        # Estimators
        self.estimate_per_command = 256  # Rough bytes per command in PST
        
        logger.info(f"SafetyBoundedPredictor initialized: "
                   f"max_memory={max_memory_mb}MB, "
                   f"max_sessions={max_sessions}")
    
    def estimate_current_size(self) -> int:
        """Estimate current memory usage"""
        return len(self.sessions) * self.estimate_per_command
    
    def learn_sequence(self, session_id: str, sequence: list) -> bool:
        """
        Learn command sequence, with graceful memory management.
        
        Returns:
            True if learned successfully
            False if memory exceeded and data was pruned (but still ok)
        """
        
        # Estimate new size
        new_data_size = len(sequence) * self.estimate_per_command
        proposed_total = self.estimate_current_size() + new_data_size
        
        # Check memory limits
        if proposed_total > self.max_memory:
            logger.warning(
                f"Memory limit approaching: "
                f"{proposed_total / 1024 / 1024:.1f}MB > {self.max_memory / 1024 / 1024:.1f}MB"
            )
            
            # Graceful prune: Remove least-recently-used 20% of sessions
            self._prune_lru_sessions(percent=0.2)
        
        # Check session limits
        if len(self.sessions) >= self.max_sessions:
            logger.warning(
                f"Session limit reached ({self.max_sessions}), "
                f"evicting oldest session"
            )
            # Remove oldest session
            oldest_id = min(self.session_timestamps, 
                           key=self.session_timestamps.get)
            self._evict_session(oldest_id)
        
        # Learn (now we have space)
        self.sessions[session_id] = sequence
        self.session_timestamps[session_id] = datetime.utcnow()
        
        return True
    
    def _prune_lru_sessions(self, percent: float = 0.2):
        """Remove least-recently-used sessions"""
        
        to_remove_count = max(1, int(len(self.sessions) * percent))
        
        # Get oldest sessions
        sorted_sessions = sorted(
            self.session_timestamps.items(),
            key=lambda x: x[1]
        )
        
        for session_id, _ in sorted_sessions[:to_remove_count]:
            self._evict_session(session_id)
            logger.info(f"Pruned session {session_id}")
    
    def _evict_session(self, session_id: str):
        """Remove a session from memory"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.session_timestamps:
            del self.session_timestamps[session_id]


class SystemHealthMonitor:
    """
    Continuously monitors system health and triggers degradation if needed.
    """
    
    def __init__(self, budgets: SystemBudgets = None):
        self.budgets = budgets or SystemBudgets()
        self.degradation_level = DegradationLevel.NORMAL
        self.last_degradation_change = datetime.utcnow()
        
        # Health history (for averaging)
        self.cpu_history = []
        self.memory_history = []
        
        logger.info("SystemHealthMonitor initialized")
    
    def get_current_health(self) -> dict:
        """Get current system health metrics"""
        
        try:
            if _HAS_PSUTIL and psutil is not None:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_percent = psutil.virtual_memory().percent
            else:
                # Safe fallback when psutil isn't available
                cpu_percent = 0.0
                memory_percent = 0.0
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "timestamp": datetime.utcnow(),
                "healthy": self._evaluate_health(cpu_percent, memory_percent)
            }
        except Exception as e:
            logger.error(f"Failed to get health metrics: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "timestamp": datetime.utcnow(),
                "healthy": True
            }
    
    def _evaluate_health(self, cpu_percent: float, memory_percent: float) -> bool:
        """Evaluate overall health"""
        
        return (cpu_percent < self.budgets.degrade_at_cpu_percent and
                memory_percent < self.budgets.degrade_at_memory_percent)
    
    def check_and_degrade(self) -> DegradationLevel:
        """
        Check health and degrade capability if needed.
        
        Never *upgrades* (only downgrades). Recovery requires manual intervention.
        """
        
        health = self.get_current_health()
        cpu = health["cpu_percent"]
        mem = health["memory_percent"]
        
        # Determine new degradation level
        if cpu > self.budgets.max_cpu_percent or \
           mem > self.budgets.max_memory_percent:
            # Critical - go to observer only
            new_level = DegradationLevel.OBSERVER_ONLY
        elif cpu > self.budgets.degrade_at_cpu_percent or \
             mem > self.budgets.degrade_at_memory_percent:
            # Elevated - go to safe mode
            new_level = DegradationLevel.SAFE_MODE
        else:
            # Normal
            new_level = DegradationLevel.NORMAL
        
        # Only degrade, never upgrade
        if self._is_more_degraded(new_level, self.degradation_level):
            old_level = self.degradation_level
            self.degradation_level = new_level
            self.last_degradation_change = datetime.utcnow()
            
            logger.warning(
                f"System degraded: {old_level} → {new_level} "
                f"(cpu={cpu:.1f}%, mem={mem:.1f}%)"
            )
        
        return self.degradation_level
    
    def _is_more_degraded(self, new: DegradationLevel, current: DegradationLevel) -> bool:
        """Check if new level is more degraded than current"""
        
        severity = {
            DegradationLevel.NORMAL: 0,
            DegradationLevel.SAFE_MODE: 1,
            DegradationLevel.OBSERVER_ONLY: 2,
            DegradationLevel.OFFLINE: 3
        }
        
        return severity[new] > severity[current]
    
    def should_skip_ai_analysis(self) -> bool:
        """Should we skip expensive AI layers?"""
        return self.degradation_level != DegradationLevel.NORMAL
    
    def should_skip_ml(self) -> bool:
        """Should we skip Machine Learning (Layer 2+)?"""
        return self.degradation_level in [
            DegradationLevel.SAFE_MODE,
            DegradationLevel.OBSERVER_ONLY
        ]
    
    def should_skip_all_processing(self) -> bool:
        """Should we skip all processing (observer mode)?"""
        return self.degradation_level in [
            DegradationLevel.OBSERVER_ONLY,
            DegradationLevel.OFFLINE
        ]


class TimeoutProtection:
    """
    Prevent any operation from hanging indefinitely.
    """
    
    def __init__(self, default_timeout_seconds: float = 5.0):
        self.default_timeout = default_timeout_seconds
    
    async def with_timeout(self, 
                          coro,
                          timeout_seconds: Optional[float] = None,
                          operation_name: str = "operation"):
        """
        Run coroutine with timeout protection.
        
        Returns:
            Result if completed in time
            None if timed out
        """
        
        timeout = timeout_seconds or self.default_timeout
        
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(
                f"Operation '{operation_name}' timed out after {timeout}s"
            )
            return None


class PassthroughFailsafe:
    """
    Ensures network traffic always passes through, even if Apate is dead.
    
    For inline deployments (not typical household), this is critical.
    """
    
    def __init__(self, 
                 forward_on_error: bool = True,
                 max_error_rate: float = 0.05):
        """
        Initialize failsafe.
        
        Args:
            forward_on_error: If True, forward traffic on any Apate error
            max_error_rate: If error rate exceeds this, auto-failover
        """
        self.forward_on_error = forward_on_error
        self.max_error_rate = max_error_rate
        
        # Error tracking
        self.total_requests = 0
        self.errors = 0
        self.last_error_time = None
    
    def record_request(self, success: bool = True):
        """Record request result"""
        self.total_requests += 1
        
        if not success:
            self.errors += 1
            self.last_error_time = datetime.utcnow()
    
    def should_failover(self) -> bool:
        """Check if error rate exceeds threshold"""
        
        if self.total_requests < 10:
            return False  # Need enough data
        
        error_rate = self.errors / self.total_requests
        
        if error_rate > self.max_error_rate:
            logger.error(
                f"Error rate {error_rate:.1%} exceeds threshold "
                f"{self.max_error_rate:.1%}, initiating failover"
            )
            return True
        
        return False
    
    def reset(self):
        """Reset error counters"""
        self.total_requests = 0
        self.errors = 0


# Integration example for honeypot system
class HouseholdSafeHoneypot:
    """
    Honeypot with household safety guarantees.
    """
    
    def __init__(self, budgets: SystemBudgets = None):
        self.budgets = budgets or SystemBudgets()
        self.health_monitor = SystemHealthMonitor(budgets)
        self.predictor = SafetyBoundedPredictor(
            max_memory_mb=budgets.max_ai_memory_mb
        )
        self.timeout = TimeoutProtection(budgets.default_timeout_seconds)
        self.failsafe = PassthroughFailsafe()
    
    async def process_request(self, 
                             session_id: str,
                             command: str) -> Optional[str]:
        """
        Process request with all safety guarantees.
        
        Returns:
            Response string if successful
            None if failed (will forward unchanged)
        """
        
        # Check system health
        degradation = self.health_monitor.check_and_degrade()
        
        if degradation == DegradationLevel.OBSERVER_ONLY:
            # Don't process, just pass through
            self.failsafe.record_request(success=True)
            return None
        
        # Try to process with timeout
        try:
            response = await self.timeout.with_timeout(
                self._generate_response(session_id, command),
                operation_name=f"process {command}"
            )
            
            self.failsafe.record_request(success=response is not None)
            return response
        
        except Exception as e:
            logger.error(f"Request processing failed: {e}")
            self.failsafe.record_request(success=False)
            return None
    
    async def _generate_response(self, session_id: str, command: str) -> str:
        """Generate honeypot response (can be slow)"""
        # Simulated AI layer processing
        await asyncio.sleep(0.01)  # Stub delay
        return f"honeypot> {command}"
