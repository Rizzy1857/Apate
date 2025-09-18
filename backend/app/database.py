"""
Database Models
---------------
SQLAlchemy models for persistent storage of honeypot data.
Includes tables for interactions, alerts, logs, and analytics.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Optional

Base = declarative_base()

class HoneypotSession(Base):
    """Represents a honeypot session"""
    __tablename__ = "honeypot_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_key = Column(String(128), unique=True, index=True, nullable=False)
    session_type = Column(String(32), nullable=False)  # ssh, http, tcp, iot
    source_ip = Column(String(45), index=True, nullable=False)  # IPv4 or IPv6
    source_port = Column(Integer)
    destination_port = Column(Integer, nullable=False)
    start_time = Column(DateTime, default=func.now(), nullable=False)
    end_time = Column(DateTime)
    is_active = Column(Boolean, default=True, nullable=False)
    user_agent = Column(Text)
    protocol_version = Column(String(32))
    client_info = Column(JSON)  # Additional client metadata
    ai_enhanced = Column(Boolean, default=False)
    risk_score = Column(Float, default=0.0)
    
    # Relationships
    interactions = relationship("HoneypotInteractionDB", back_populates="session")
    alerts = relationship("AlertDB", back_populates="session")

class HoneypotInteractionDB(Base):
    """Represents an interaction within a session"""
    __tablename__ = "honeypot_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("honeypot_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    interaction_type = Column(String(32), nullable=False)  # command, login_attempt, request
    data = Column(Text, nullable=False)
    response = Column(Text)
    success = Column(Boolean)
    ai_generated_response = Column(Boolean, default=False)
    honeytoken_triggered = Column(String(64))  # ID of triggered honeytoken
    meta = Column(JSON)
    
    # Relationships
    session = relationship("HoneypotSession", back_populates="interactions")

class AlertDB(Base):
    """Represents security alerts"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("honeypot_sessions.id"))
    alert_type = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False)  # low, medium, high, critical
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    source_ip = Column(String(45), index=True, nullable=False)
    indicators = Column(JSON)  # IOCs, patterns, etc.
    resolved = Column(Boolean, default=False)
    resolved_by = Column(String(128))
    resolved_at = Column(DateTime)
    
    # Relationships
    session = relationship("HoneypotSession", back_populates="alerts")

class HoneytokenDB(Base):
    """Represents deployed honeytokens"""
    __tablename__ = "honeytokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token_id = Column(String(64), unique=True, index=True, nullable=False)
    token_type = Column(String(32), nullable=False)  # credentials, api_key, ssh_key, etc.
    token_value = Column(Text, nullable=False)
    deployment_context = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    times_triggered = Column(Integer, default=0)
    first_triggered_at = Column(DateTime)
    last_triggered_at = Column(DateTime)
    triggered_by_ips = Column(JSON)  # List of IPs that triggered this token

class AttackerProfileDB(Base):
    """Represents attacker profiles built over time"""
    __tablename__ = "attacker_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    source_ip = Column(String(45), unique=True, index=True, nullable=False)
    first_seen = Column(DateTime, default=func.now(), nullable=False)
    last_seen = Column(DateTime, default=func.now(), nullable=False)
    session_count = Column(Integer, default=1)
    total_interactions = Column(Integer, default=0)
    common_commands = Column(JSON)  # Most used commands
    common_user_agents = Column(JSON)
    attack_patterns = Column(JSON)  # Identified patterns
    risk_score = Column(Float, default=0.0)
    country = Column(String(2))  # ISO country code
    asn = Column(Integer)
    organization = Column(String(256))
    is_tor = Column(Boolean, default=False)
    is_vpn = Column(Boolean, default=False)
    tags = Column(JSON)  # Custom tags for classification

class SystemLogDB(Base):
    """System logs for audit and debugging"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    level = Column(String(16), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name = Column(String(128), nullable=False)
    message = Column(Text, nullable=False)
    module = Column(String(128))
    function = Column(String(128))
    line_number = Column(Integer)
    extra_data = Column(JSON)

class ThreatIntelDB(Base):
    """Threat intelligence data"""
    __tablename__ = "threat_intel"
    
    id = Column(Integer, primary_key=True, index=True)
    indicator = Column(String(256), unique=True, index=True, nullable=False)
    indicator_type = Column(String(32), nullable=False)  # ip, domain, hash, etc.
    threat_type = Column(String(64))  # malware, botnet, scanner, etc.
    confidence = Column(Float, default=0.0)  # 0.0 to 1.0
    first_seen = Column(DateTime, default=func.now(), nullable=False)
    last_seen = Column(DateTime, default=func.now(), nullable=False)
    source = Column(String(128))  # Source of intelligence
    description = Column(Text)
    meta = Column(JSON)
    is_active = Column(Boolean, default=True)

class ConfigurationDB(Base):
    """Runtime configuration storage"""
    __tablename__ = "configuration"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(128), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    value_type = Column(String(16), nullable=False)  # string, int, float, bool, json
    description = Column(Text)
    category = Column(String(64))
    is_sensitive = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# Utility functions for working with the database models

def create_session_from_pydantic(session_data: dict) -> HoneypotSession:
    """Create a database session from Pydantic model data"""
    return HoneypotSession(
        session_key=session_data.get("session_key"),
        session_type=session_data.get("session_type"),
        source_ip=session_data.get("source_ip"),
        source_port=session_data.get("source_port"),
        destination_port=session_data.get("destination_port"),
        user_agent=session_data.get("user_agent"),
        protocol_version=session_data.get("protocol_version"),
        client_info=session_data.get("client_info"),
        ai_enhanced=session_data.get("ai_enhanced", False),
        risk_score=session_data.get("risk_score", 0.0)
    )

def create_interaction_from_pydantic(interaction_data: dict, session_id: int) -> HoneypotInteractionDB:
    """Create a database interaction from Pydantic model data"""
    return HoneypotInteractionDB(
        session_id=session_id,
        interaction_type=interaction_data.get("interaction_type"),
        data=interaction_data.get("data"),
        response=interaction_data.get("response"),
        success=interaction_data.get("success"),
        ai_generated_response=interaction_data.get("ai_generated_response", False),
        honeytoken_triggered=interaction_data.get("honeytoken_triggered"),
    meta=interaction_data.get("metadata")
    )

def create_alert_from_pydantic(alert_data: dict, session_id: Optional[int] = None) -> AlertDB:
    """Create a database alert from Pydantic model data"""
    return AlertDB(
        session_id=session_id,
        alert_type=alert_data.get("alert_type"),
        severity=alert_data.get("severity"),
        title=alert_data.get("title"),
        description=alert_data.get("description"),
        source_ip=alert_data.get("source_ip"),
        indicators=alert_data.get("indicators"),
        resolved=alert_data.get("resolved", False)
    )
