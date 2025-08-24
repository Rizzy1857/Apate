"""
FastAPI Entrypoint
------------------
This file starts the FastAPI server and exposes a root endpoint for health/status checks.
Main server that orchestrates the honeypot services and API endpoints.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from datetime import datetime, UTC

from .honeypot.ssh_emulator import SSHEmulator
from .honeypot.http_emulator import HTTPEmulator
from .routes import router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mirage Honeypot",
    description="Adaptive LLM-driven honeypot system",
    version="1.0.0"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include additional routes
app.include_router(router, prefix="/api/v1", tags=["honeypot"])

# Initialize honeypot components
ssh_emulator = SSHEmulator()
http_emulator = HTTPEmulator()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Mirage Honeypot",
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {
            "ssh_emulator": "active",
            "http_emulator": "active",
            "ai_engine": "active"
        }
    }

@app.get("/status")
async def get_status():
    """Detailed status of all honeypot components"""
    return {
        "system": "healthy",
        "uptime": "active",
        "honeypots": {
            "ssh": {"status": "listening", "port": 2222},
            "http": {"status": "listening", "port": 8080},
            "tcp_echo": {"status": "listening", "port": 7878}
        },
        "ai_engine": {"status": "ready", "model": "adaptive"},
        "logging": {"status": "active", "level": "INFO"}
    }

@app.post("/honeypot/ssh/interact")
async def ssh_interact(command: str, session_id: str = "default"):
    """Simulate SSH command interaction"""
    try:
        response = await ssh_emulator.handle_command(command, session_id)
        return {
            "success": True,
            "output": response,
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat()
        }
    except Exception as e:
        logger.error(f"SSH interaction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/honeypot/http/login")
async def http_login(username: str, password: str, ip: str = "unknown"):
    """Simulate HTTP login attempt"""
    try:
        response = await http_emulator.handle_login(username, password, ip)
        return response
    except Exception as e:
        logger.error(f"HTTP login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts(limit: int = 10):
    """Get recent security alerts"""
    # Placeholder for alert retrieval
    return {
        "alerts": [],
        "count": 0,
        "message": "Alert system ready - no active threats detected"
    }

@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get recent honeypot interaction logs"""
    # Placeholder for log retrieval
    return {
        "logs": [],
        "count": 0,
        "message": "Logging system active - awaiting interactions"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
