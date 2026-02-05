"""
Pydantic Models
---------------
Data models for API requests/responses, alerts, and logging.
Defines the structure for honeypot interactions and intelligence data.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class InteractionType(str, Enum):
    SSH = "ssh"
    HTTP = "http"
    TCP = "tcp"
    HONEYTOKEN = "honeytoken"

class Alert(BaseModel):
    """Security alert model"""
    id: str = Field(..., description="Unique alert identifier")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Detailed alert description")
    source_ip: str = Field(..., description="Source IP address")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional alert data")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Log(BaseModel):
    """Honeypot interaction log model"""
    id: str = Field(..., description="Unique log identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_ip: str = Field(..., description="Source IP address")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    command: Optional[str] = Field(None, description="Command executed (if applicable)")
    response: Optional[str] = Field(None, description="System response")
    session_id: str = Field(..., description="Session identifier")
    user_agent: Optional[str] = Field(None, description="User agent (for HTTP)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional log data")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class HoneypotInteraction(BaseModel):
    """Generic honeypot interaction model"""
    session_id: str = Field(..., description="Session identifier")
    source_ip: str = Field(..., description="Source IP address")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    data: Dict[str, Any] = Field(..., description="Interaction data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class SSHCommandRequest(BaseModel):
    """SSH command request model"""
    command: str = Field(..., description="SSH command to execute")
    session_id: str = Field(default="default", description="SSH session identifier")
    
class HTTPLoginRequest(BaseModel):
    """HTTP login request model"""
    username: str = Field(..., description="Login username")
    password: str = Field(..., description="Login password")
    ip: str = Field(default="unknown", description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")

class AttackerProfile(BaseModel):
    """Attacker profiling model"""
    ip: str = Field(..., description="Attacker IP address")
    first_seen: datetime = Field(..., description="First interaction timestamp")
    last_seen: datetime = Field(..., description="Last interaction timestamp")
    interaction_count: int = Field(default=0, description="Total interactions")
    commands_used: List[str] = Field(default_factory=list, description="Commands attempted")
    threat_score: float = Field(default=0.0, description="Calculated threat score")
    geolocation: Dict[str, Any] = Field(default_factory=dict, description="IP geolocation data")
    threat_intel: Dict[str, Any] = Field(default_factory=dict, description="External threat intelligence")
    
class HoneytokenTrigger(BaseModel):
    """Honeytoken trigger event model"""
    token_id: str = Field(..., description="Honeytoken identifier")
    token_type: str = Field(..., description="Type of honeytoken (creds, file, etc.)")
    triggered_by: str = Field(..., description="IP address that triggered token")
    trigger_action: str = Field(..., description="Action that triggered the token")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
