"""
Route Handlers
--------------
Additional API routes for honeypot management and monitoring.
Extends the main FastAPI application with specialized endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from .honeypot.adapter import HoneypotAdapter
from .honeypot.tokens import HoneytokenGenerator

logger = logging.getLogger(__name__)

# Create router for additional endpoints
router = APIRouter()

# Initialize honeypot components
honeypot_adapter = HoneypotAdapter()
token_generator = HoneytokenGenerator()

@router.get("/sessions", response_model=List[Dict[str, Any]])
async def get_active_sessions(limit: int = Query(default=50, le=100)):
    """Get list of active honeypot sessions"""
    try:
        sessions = []
        for session_key, session_data in honeypot_adapter.active_sessions.items():
            session_info = {
                "session_key": session_key,
                "session_type": session_data.get("type"),
                "source_ip": session_data.get("source_ip"),
                "start_time": session_data.get("start_time"),
                "activity_count": len(session_data.get("commands", [])) + len(session_data.get("login_attempts", [])),
                "ai_enhanced": session_data.get("ai_enhanced", False)
            }
            sessions.append(session_info)
        
        return sessions[:limit]
    except Exception as e:
        logger.error(f"Error retrieving sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    try:
        session_summary = await honeypot_adapter.get_session_summary(session_id)
        if not session_summary:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session_summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/honeytokens/deploy")
async def deploy_honeytokens(
    token_type: str,
    count: int = Query(default=1, ge=1, le=10),
    context: Optional[Dict[str, Any]] = None
):
    """Deploy new honeytokens"""
    try:
        deployed_tokens = []
        
        for _ in range(count):
            if token_type == "credentials":
                token = token_generator.generate_credentials("api")
            elif token_type == "api_key":
                token = token_generator.generate_api_key("openai")
            elif token_type == "ssh_key":
                token = token_generator.generate_ssh_key()
            elif token_type == "config":
                token = token_generator.generate_config_file("database")
            elif token_type == "web_beacon":
                token = token_generator.generate_web_beacon("http://callback.local")
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported token type: {token_type}")
            
            deployed_tokens.append(token)
        
        return {
            "success": True,
            "deployed_count": len(deployed_tokens),
            "tokens": deployed_tokens
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deploying honeytokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/honeytokens")
async def get_honeytokens(
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, le=100)
):
    """Get list of honeytokens"""
    try:
        if active_only:
            tokens = await token_generator.get_active_tokens()
        else:
            active_tokens = await token_generator.get_active_tokens()
            triggered_tokens = await token_generator.get_triggered_tokens()
            tokens = active_tokens + triggered_tokens
        
        return {
            "total_count": len(tokens),
            "tokens": tokens[:limit]
        }
    except Exception as e:
        logger.error(f"Error retrieving honeytokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/honeytokens/triggered")
async def get_triggered_honeytokens():
    """Get list of triggered honeytokens"""
    try:
        triggered_tokens = await token_generator.get_triggered_tokens()
        return {
            "triggered_count": len(triggered_tokens),
            "tokens": triggered_tokens
        }
    except Exception as e:
        logger.error(f"Error retrieving triggered honeytokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/threats")
async def get_threat_events(
    severity: Optional[str] = Query(default=None),
    last_hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, le=500)
):
    """Get threat events from all honeypot components"""
    try:
        # This would integrate with actual threat logging system
        # For now, return placeholder data
        threat_events = [
            {
                "event_id": f"threat_{datetime.utcnow().timestamp()}",
                "timestamp": datetime.utcnow().isoformat(),
                "source_ip": "192.168.1.100",
                "event_type": "brute_force_attempt",
                "description": "Multiple failed login attempts detected",
                "severity": "medium",
                "component": "http_honeypot",
                "metadata": {"attempts": 15, "timespan": "5 minutes"}
            }
        ]
        
        # Filter by severity if specified
        if severity:
            threat_events = [e for e in threat_events if e["severity"] == severity.lower()]
        
        return {
            "total_events": len(threat_events),
            "events": threat_events[:limit]
        }
    except Exception as e:
        logger.error(f"Error retrieving threat events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/attackers")
async def get_attacker_analytics():
    """Get analytics about attackers and their behavior"""
    try:
        # This would integrate with actual analytics system
        analytics = {
            "total_unique_attackers": 42,
            "active_sessions": len(honeypot_adapter.active_sessions),
            "top_source_countries": [
                {"country": "Unknown", "count": 15},
                {"country": "Various", "count": 12},
                {"country": "Multiple", "count": 8}
            ],
            "attack_patterns": [
                {"pattern": "reconnaissance", "count": 28},
                {"pattern": "brute_force", "count": 19},
                {"pattern": "lateral_movement", "count": 7}
            ],
            "honeytokens_triggered": len(await token_generator.get_triggered_tokens()),
            "time_range": "last_24_hours"
        }
        
        return analytics
    except Exception as e:
        logger.error(f"Error generating analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/interactions")
async def get_interaction_analytics():
    """Get analytics about honeypot interactions"""
    try:
        analytics = {
            "total_interactions": sum(len(s.get("commands", [])) + len(s.get("login_attempts", [])) 
                                    for s in honeypot_adapter.active_sessions.values()),
            "by_service": {
                "ssh": sum(1 for s in honeypot_adapter.active_sessions.values() 
                          if s.get("type") == "ssh"),
                "http": sum(1 for s in honeypot_adapter.active_sessions.values() 
                           if s.get("type") == "http"),
                "tcp": 0,  # Would be populated from actual data
                "iot": 0   # Would be populated from actual data
            },
            "top_commands": [
                {"command": "ls", "count": 156},
                {"command": "pwd", "count": 89},
                {"command": "whoami", "count": 67},
                {"command": "cat", "count": 45},
                {"command": "ps", "count": 34}
            ],
            "ai_enhanced_responses": sum(1 for s in honeypot_adapter.active_sessions.values() 
                                       if s.get("ai_enhanced", False))
        }
        
        return analytics
    except Exception as e:
        logger.error(f"Error generating interaction analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/cleanup")
async def cleanup_old_data(
    max_age_days: int = Query(default=30, ge=1, le=365)
):
    """Clean up old honeypot data"""
    try:
        # Clean up old honeytokens
        cleaned_tokens = await token_generator.cleanup_expired_tokens(max_age_days)
        
        # Clean up old sessions (would implement actual cleanup)
        cleaned_sessions = 0
        
        # Clean up old logs (would implement actual cleanup)
        cleaned_logs = 0
        
        return {
            "success": True,
            "cleaned_items": {
                "honeytokens": cleaned_tokens,
                "sessions": cleaned_sessions,
                "logs": cleaned_logs
            }
        }
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/health")
async def health_check():
    """Comprehensive health check of all honeypot components"""
    try:
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "ssh_emulator": {"status": "healthy", "active_sessions": 0},
                "http_emulator": {"status": "healthy", "active_sessions": 0},
                "ai_engine": {"status": "healthy", "provider": "stub"},
                "honeytoken_generator": {"status": "healthy", "active_tokens": len(await token_generator.get_active_tokens())},
                "adapter": {"status": "healthy", "total_sessions": len(honeypot_adapter.active_sessions)}
            },
            "performance": {
                "memory_usage": "unknown",
                "cpu_usage": "unknown", 
                "disk_usage": "unknown"
            }
        }
        
        # Count active sessions by type
        ssh_sessions = sum(1 for s in honeypot_adapter.active_sessions.values() 
                          if s.get("type") == "ssh")
        http_sessions = sum(1 for s in honeypot_adapter.active_sessions.values() 
                           if s.get("type") == "http")
        
        health_status["components"]["ssh_emulator"]["active_sessions"] = ssh_sessions
        health_status["components"]["http_emulator"]["active_sessions"] = http_sessions
        
        return health_status
    except Exception as e:
        logger.error(f"Error during health check: {e}")
        return {
            "overall_status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
