"""Unified threat scoring utility module"""
import logging

logger = logging.getLogger(__name__)


def calculate_risk_level(score: int) -> str:
    """Calculate risk level from score (0-100+)"""
    if score >= 60:
        return "critical"
    elif score >= 40:
        return "high"
    elif score >= 20:
        return "medium"
    elif score > 0:
        return "low"
    else:
        return "benign"


def calculate_risk_level_event(score: int) -> str:
    """Calculate risk level from event score"""
    if score >= 50:
        return "critical"
    elif score >= 30:
        return "high"
    elif score >= 15:
        return "medium"
    elif score > 0:
        return "low"
    else:
        return "info"
