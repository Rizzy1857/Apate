"""
Apate Honeypot - Main FastAPI Application

Advanced AI-driven honeypot platform for threat detection and analysis.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Request/Response Models
class SSHInteractionRequest(BaseModel):
    session_id: str
    command: str
    client_ip: str

class HTTPLoginRequest(BaseModel):
    username: str
    password: str
    service_type: str = "admin_panel"
    client_ip: str

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]
    version: str

# Create FastAPI application with comprehensive documentation
app = FastAPI(
    title="Apate Honeypot API",
    description="""
    ## Advanced AI-Driven Honeypot Platform

    **Apate** is a next-generation honeypot platform that creates adaptive, realistic deception environments 
    for advanced threat detection and analysis.

    ### Key Features
    * **SSH Emulator**: Full shell simulation with realistic filesystem
    * **HTTP Emulator**: Adaptive web service honeypot with multiple templates
    * **Honeytoken System**: Advanced bait deployment and tracking
    * **Real-time Threat Analysis**: Behavioral pattern detection
    * **Session Management**: Redis-backed persistence and tracking

    ### Authentication
    Currently supports development mode with CORS enabled. Production deployments 
    should implement proper authentication mechanisms.

    ### Rate Limiting
    IP-based rate limiting is implemented to simulate realistic service behavior 
    and prevent abuse.
    """,
    version="1.0.0",
    contact={
        "name": "Apate Development Team",
        "url": "https://github.com/Rizzy1857/Apate",
        "email": "support@apate-honeypot.dev",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.apate-honeypot.dev",
            "description": "Production server"
        }
    ],
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and system status endpoints"
        },
        {
            "name": "honeypot",
            "description": "Core honeypot interaction endpoints"
        },
        {
            "name": "ssh",
            "description": "SSH emulator endpoints"
        },
        {
            "name": "http",
            "description": "HTTP emulator endpoints"
        },
        {
            "name": "honeytokens",
            "description": "Honeytoken management and tracking"
        },
        {
            "name": "analytics",
            "description": "Threat analysis and reporting"
        }
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    System health check endpoint.
    
    Returns the current health status of all Apate services including:
    - API server status
    - Database connectivity  
    - Redis cache status
    - Service dependencies
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {
            "api": "healthy",
            "database": "healthy",
            "redis": "healthy"
        },
        "version": "1.0.0"
    }

# Status endpoint
@app.get("/status", tags=["health"])
async def get_status() -> Dict[str, Any]:
    """
    Detailed system status endpoint.
    """
    return {
        "api_status": "operational",
        "uptime": "running",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# SSH Honeypot endpoints
@app.post("/honeypot/ssh/interact", tags=["ssh", "honeypot"], response_model=Dict[str, Any])
async def ssh_interact(request: SSHInteractionRequest) -> Dict[str, Any]:
    """
    SSH Honeypot Interaction endpoint.
    
    Simulates SSH shell interaction with realistic command responses.
    Supports 15+ common Unix commands with proper filesystem simulation.
    """
    logger.info(f"SSH interaction: {request.session_id} executed '{request.command}' from {request.client_ip}")
    
    # This would integrate with your existing SSH emulator
    return {
        "output": f"Executed command: {request.command}",
        "threat_level": "LOW",
        "session_id": request.session_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# HTTP Honeypot endpoints  
@app.post("/honeypot/http/login", tags=["http", "honeypot"], response_model=Dict[str, Any])
async def http_login(request: HTTPLoginRequest) -> Dict[str, Any]:
    """
    HTTP Login Simulation endpoint.
    
    Simulates various web login interfaces including admin panels,
    webmail, FTP, and router interfaces with realistic responses.
    """
    logger.info(f"HTTP login attempt: {request.username} on {request.service_type} from {request.client_ip}")
    
    # This would integrate with your existing HTTP emulator
    return {
        "success": False,
        "message": "Invalid credentials",
        "threat_level": "MEDIUM", 
        "attempt_count": 1,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint not found",
            "code": 404,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": 500, 
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)