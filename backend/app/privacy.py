"""
Privacy-First Telemetry Architecture
=====================================

DESIGN PRINCIPLE: Process locally, ship summary only.

STATUS: DORMANT GUARDRAIL (not active in data pipeline)

This module DEFINES privacy invariants but is NOT collecting/shipping data yet.

When active (Q1 2026+):
- Enforces raw data stays local (7-day lock)
- Aggregates are privacy-safe before any cloud export
- System continues functioning without telemetry

Until Q1 2026:
- Exists as a boundary/spec
- Default config: HOUSEHOLD mode (0% cloud)
- Ready to wrap telemetry pipeline when needed
"""

import json
import logging
import hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from collections import defaultdict
from enum import Enum
import uuid

try:
    from scipy.stats import laplace
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)


class PrivacyMode(str, Enum):
    """Privacy posture options"""
    HOUSEHOLD = "household"      # 100% local, no cloud
    ENTERPRISE_LOCAL = "enterprise_local"  # On-prem only
    ENTERPRISE_CLOUD = "enterprise_cloud"  # Cloud reporting allowed
    AIR_GAPPED = "air_gapped"    # No internet at all


@dataclass
class TelemetryConfig:
    """Telemetry configuration with privacy controls"""
    
    # Basic settings
    enabled: bool = True
    privacy_mode: PrivacyMode = PrivacyMode.HOUSEHOLD
    
    # Cloud endpoint (only used if privacy_mode allows)
    cloud_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    
    # Local buffering
    max_cached_metrics_mb: int = 100
    cache_flush_interval_seconds: int = 3600  # 1 hour
    
    # Differential privacy (for edge cases)
    use_differential_privacy: bool = False
    differential_privacy_epsilon: float = 1.0  # Privacy budget
    
    # Data retention
    max_local_history_days: int = 7
    
    def is_cloud_enabled(self) -> bool:
        """Returns True if telemetry should reach cloud"""
        return self.enabled and \
               self.privacy_mode in [
                   PrivacyMode.ENTERPRISE_CLOUD
               ] and \
               self.cloud_endpoint is not None


@dataclass
class AggregatedMetrics:
    """Privacy-safe aggregated metrics (OK to ship)"""
    
    timestamp: datetime
    device_id_hash: str  # Hashed, not raw
    
    # Command family distribution (no commands, just categories)
    commands_by_family: Dict[str, int] = field(default_factory=dict)
    
    # Session statistics
    sessions_total: int = 0
    sessions_per_hour: float = 0.0
    avg_session_duration_seconds: float = 0.0
    
    # Attack pattern distribution
    attack_patterns: Dict[str, float] = field(default_factory=dict)  # Percentages
    
    # System health
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_hours: float = 0.0
    
    # Model performance (no training data, just accuracy metrics)
    layer1_accuracy: float = 0.0
    layer2_accuracy: float = 0.0
    
    # Honeypot engagement (counts only, no details)
    honeypot_accesses: int = 0
    mttd_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-safe dict"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "device_id_hash": self.device_id_hash,
            "commands_by_family": self.commands_by_family,
            "sessions": {
                "total": self.sessions_total,
                "per_hour": self.sessions_per_hour,
                "avg_duration_seconds": self.avg_session_duration_seconds
            },
            "attack_patterns": self.attack_patterns,
            "system_health": {
                "cpu_percent": self.cpu_percent,
                "memory_mb": self.memory_mb,
                "uptime_hours": self.uptime_hours
            },
            "model_performance": {
                "layer1_accuracy": self.layer1_accuracy,
                "layer2_accuracy": self.layer2_accuracy
            },
            "honeypot": {
                "accesses": self.honeypot_accesses,
                "mttd_seconds": self.mttd_seconds
            }
        }


class DifferentialPrivacyGuard:
    """
    Add Laplacian noise to metrics to prevent inference attacks.
    
    Use sparingly—only if aggregates alone aren't sufficient.
    """
    
    def __init__(self, epsilon: float = 1.0):
        """
        epsilon controls privacy-utility tradeoff
        
        - epsilon >> 1: More noise, less useful data
        - epsilon ~= 1: Standard "reasonable privacy"
        - epsilon << 1: Less noise, higher privacy leak risk
        
        Standard guidance: epsilon = 0.5 to 2.0
        """
        if not HAS_SCIPY:
            logger.warning("scipy not available, DifferentialPrivacyGuard disabled")
        
        self.epsilon = epsilon
    
    def sanitize_metric(self, 
                       raw_value: float, 
                       sensitivity: float = 1.0,
                       min_value: float = 0.0,
                       max_value: Optional[float] = None) -> float:
        """
        Add Laplacian noise to metric before shipping.
        
        Args:
            raw_value: The true value
            sensitivity: How much the metric can change per unit change in data
            min_value: Minimum allowed value (clipping)
            max_value: Maximum allowed value (clipping)
        
        Returns:
            Noisy value safe for sharing
        """
        if not HAS_SCIPY:
            # If scipy unavailable, just return original (no privacy protection)
            logger.debug("Returning raw value (scipy unavailable)")
            return raw_value
        
        # Calculate noise scale
        scale = sensitivity / self.epsilon
        
        # Sample noise from Laplace distribution
        noise = laplace.rvs(loc=0, scale=scale)
        
        # Add noise
        noisy_value = raw_value + noise
        
        # Clip to valid range
        noisy_value = max(min_value, noisy_value)
        if max_value is not None:
            noisy_value = min(max_value, noisy_value)
        
        return noisy_value


class PrivacyPreservingTelemetry:
    """
    On-device summarization prevents raw data from leaving the network.
    
    Invariant: Raw data never exported unless explicitly requested by user.
    """
    
    def __init__(self, 
                 config: TelemetryConfig,
                 device_name: str = "apate-device"):
        """
        Initialize privacy-preserving telemetry.
        
        Args:
            config: TelemetryConfig with privacy settings
            device_name: Friendly name for this device
        """
        self.config = config
        self.device_name = device_name
        
        # Generate hashed device ID (not personally identifiable)
        self.device_id_hash = hashlib.sha256(
            f"{device_name}{datetime.utcnow().date()}".encode()
        ).hexdigest()[:16]
        
        # Raw data (NEVER exported without user consent)
        self.raw_data: Dict[str, Dict[str, Any]] = {}
        self.raw_data_lock_until: datetime = datetime.utcnow() + timedelta(days=7)
        
        # Aggregates (safe to ship)
        self.aggregates = AggregatedMetrics(
            timestamp=datetime.utcnow(),
            device_id_hash=self.device_id_hash
        )
        
        # Offline buffer (for cloud telemetry)
        self.offline_buffer: List[Dict[str, Any]] = []
        
        # Differential privacy
        self.dp_guard = DifferentialPrivacyGuard(
            epsilon=config.differential_privacy_epsilon
        ) if config.use_differential_privacy else None
        
        logger.info(f"Privacy-preserving telemetry initialized: "
                   f"mode={config.privacy_mode}, "
                   f"cloud_enabled={config.is_cloud_enabled()}")
    
    def record_ssh_command(self, 
                          source_ip: str,
                          command: str,
                          output_length: int,
                          execution_ms: float):
        """
        Record SSH command execution.
        
        Raw data: Stays local only
        Aggregated: Command family + execution time stats
        """
        
        # Store raw (local only)
        event_id = str(uuid.uuid4())
        self.raw_data[event_id] = {
            "timestamp": datetime.utcnow(),
            "source_ip": source_ip,  # Never shipped
            "command": command,      # Never shipped
            "output_length": output_length,
            "execution_ms": execution_ms
        }
        
        # Update aggregates
        command_family = self._classify_command_family(command)
        self.aggregates.commands_by_family[command_family] = \
            self.aggregates.commands_by_family.get(command_family, 0) + 1
    
    def record_login_attempt(self,
                            source_ip: str,
                            username: str,
                            success: bool,
                            protocol: str = "ssh"):
        """
        Record login attempt.
        
        Raw data: Stays local (IP, username never shipped)
        Aggregated: Success rate only
        """
        
        # Store raw (local only)
        event_id = str(uuid.uuid4())
        self.raw_data[event_id] = {
            "timestamp": datetime.utcnow(),
            "source_ip": source_ip,  # Never shipped
            "username": username,    # Never shipped
            "success": success,
            "protocol": protocol
        }
    
    def record_session(self,
                       duration_seconds: float,
                       session_type: str,  # "ssh", "http"
                       attacked: bool = False):
        """Record session statistics (aggregate-safe)"""
        
        self.aggregates.sessions_total += 1
        self.aggregates.avg_session_duration_seconds = \
            (self.aggregates.avg_session_duration_seconds + duration_seconds) / 2
        
        if attacked:
            self.aggregates.honeypot_accesses += 1
    
    def record_system_health(self,
                            cpu_percent: float,
                            memory_mb: float,
                            uptime_hours: float):
        """Record system health (safe to ship)"""
        
        self.aggregates.cpu_percent = cpu_percent
        self.aggregates.memory_mb = memory_mb
        self.aggregates.uptime_hours = uptime_hours
    
    def record_model_performance(self,
                                layer1_accuracy: float,
                                layer2_accuracy: float):
        """Record model accuracy (safe to ship)"""
        
        self.aggregates.layer1_accuracy = layer1_accuracy
        self.aggregates.layer2_accuracy = layer2_accuracy
    
    def record_mttd(self, seconds: float):
        """Record mean time to discovery"""
        self.aggregates.mttd_seconds = seconds
    
    def _classify_command_family(self, command: str) -> str:
        """
        Classify command into family (reconnaissance, lateral, etc.)
        
        Never ships raw command, only the family.
        """
        cmd_base = command.split()[0].lower() if command else "unknown"
        
        families = {
            "reconnaissance": ["ls", "ps", "netstat", "whoami", "id", "uname"],
            "lateral_movement": ["ssh", "scp", "rsync", "ping"],
            "persistence": ["crontab", "systemctl", "service"],
            "data_exfiltration": ["wget", "curl", "nc", "tar", "zip"],
            "privilege_escalation": ["sudo", "su"],
            "error": ["command not found", "error", "denied"]
        }
        
        for family, commands in families.items():
            if cmd_base in commands:
                return family
        
        return "other"
    
    def generate_telemetry_packet(self) -> Dict[str, Any]:
        """
        Generate privacy-safe telemetry packet for cloud upload.
        
        This is the ONLY data that should ever leave the device.
        """
        
        if not self.config.is_cloud_enabled():
            raise PermissionError(
                f"Cloud telemetry disabled (mode={self.config.privacy_mode})"
            )
        
        # Get current aggregates
        packet = {
            "version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "device_id_hash": self.device_id_hash,
        }
        
        # Add metrics
        metrics = self.aggregates.to_dict()
        
        # Apply differential privacy if enabled
        if self.dp_guard is not None:
            metrics["sessions"]["total"] = int(
                self.dp_guard.sanitize_metric(
                    metrics["sessions"]["total"],
                    sensitivity=1.0,
                    min_value=0
                )
            )
        
        packet["metrics"] = metrics
        
        logger.debug(f"Generated telemetry packet: {len(json.dumps(packet))} bytes")
        
        return packet
    
    def export_local_data(self,
                         output_path: str,
                         include_raw: bool = False) -> bool:
        """
        Export data for local analysis.
        
        Raw data only exported if:
        1. User explicitly requests it
        2. Mode is not cloud-enabled (privacy protection)
        
        Args:
            output_path: Where to write the export
            include_raw: Include raw (non-aggregated) data
        
        Returns:
            True if export succeeded
        """
        
        if include_raw and self.config.is_cloud_enabled():
            logger.error("Raw data export blocked: cloud mode enabled")
            return False
        
        export_data = {}
        
        if include_raw:
            # User explicitly requested raw data
            if self.raw_data:
                logger.warning(f"Exporting raw data ({len(self.raw_data)} events)")
                export_data["raw_events"] = self.raw_data
            else:
                logger.info("No raw data to export")
        
        # Always include aggregates
        export_data["aggregates"] = self.aggregates.to_dict()
        
        try:
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            logger.info(f"Data exported to {output_path}")
            return True
        except IOError as e:
            logger.error(f"Export failed: {e}")
            return False
    
    def purge_old_raw_data(self, older_than_days: int = 7):
        """
        Remove raw data older than threshold.
        
        Privacy safety: Prevents accumulation of raw data.
        """
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        
        to_delete = []
        for event_id, event_data in self.raw_data.items():
            if event_data.get("timestamp", datetime.utcnow()) < cutoff:
                to_delete.append(event_id)
        
        for event_id in to_delete:
            del self.raw_data[event_id]
        
        if to_delete:
            logger.info(f"Purged {len(to_delete)} old raw events")
