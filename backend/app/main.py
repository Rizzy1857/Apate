"""
FastAPI Entrypoint
------------------
This file starts the FastAPI server and exposes a root endpoint for health/status checks.
Main server that orchestrates the honeypot services and API endpoints.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import asyncio
import uvicorn
from datetime import datetime, UTC
import os
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from .honeypot.ssh_emulator import SSHEmulator
from .honeypot.http_emulator import HTTPEmulator
from .routes import router
# DB init is imported lazily in startup to avoid hard dependency at import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mirage Honeypot",
    description=(
        "Adaptive LLM-driven honeypot system.\n\n"
        "Key Features:\n"
        "- SSH Emulator: Realistic command handling and filesystem\n"
        "- HTTP Emulator: Adaptive login pages and banners\n"
        "- Honeytokens: Credentials, API keys, SSH keys, config files, beacons\n"
        "- AI Adapter: Stubbed integration ready for providers\n"
    ),
    version="1.0.0",
    contact={
        "name": "Mirage/Apate Team",
        "url": "https://github.com/Rizzy1857/Apate",
    },
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

# JSON request models
class SSHInteractionRequest(BaseModel):
    command: str
    session_id: str = "default"

class HTTPLoginRequest(BaseModel):
    username: str
    password: str
    ip: str = "unknown"

# Serve static directory if present (optional)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static", html=False), name="static")

# Suppress browser icon 404s with empty 204 responses
@app.get("/favicon.ico", include_in_schema=False)
async def _favicon() -> Response:
    return Response(status_code=204)

@app.get("/apple-touch-icon.png", include_in_schema=False)
async def _apple_touch_icon() -> Response:
    return Response(status_code=204)

@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
async def _apple_touch_icon_pre() -> Response:
    return Response(status_code=204)

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
async def ssh_interact(body: SSHInteractionRequest):
    """Simulate SSH command interaction (JSON body)."""
    try:
        response = await ssh_emulator.handle_command(body.command, body.session_id)
        # Best-effort interaction logging
        try:
            from .db_manager import log_interaction  # lazy import
            await log_interaction(
                service="ssh",
                payload={"session_id": body.session_id, "command": body.command, "output": response},
            )
        except Exception:
            pass
        return {
            "success": True,
            "output": response,
            "session_id": body.session_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"SSH interaction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/honeypot/http/login")
async def http_login(body: HTTPLoginRequest):
    """Simulate HTTP login attempt (JSON body)."""
    try:
        result = await http_emulator.handle_login(body.username, body.password, body.ip)
        # Best-effort alerting for suspicious attempts
        try:
            from .db_manager import create_alert, log_interaction  # lazy import
            from .notifier import notify_alert
            await log_interaction(
                service="http",
                payload={"username": body.username, "ip": body.ip, "result": result},
            )
            if result.get("threat_level") in {"HIGH", "CRITICAL"}:  # escalate
                msg = f"Suspicious login for {body.username} from {body.ip}"
                await create_alert(
                    level=result["threat_level"],
                    message=msg,
                    meta=result,
                )
                await notify_alert(result["threat_level"], msg, result)
        except Exception:
            pass
        return result
    except Exception as e:
        logger.error(f"HTTP login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts(limit: int = 10):
    """Get recent security alerts from DB if available, else empty list."""
    try:
        from .db_manager import get_recent_alerts  # lazy import
        alerts = await get_recent_alerts(limit)
        return {"alerts": alerts, "count": len(alerts)}
    except Exception:
        return {"alerts": [], "count": 0}

@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get recent interaction logs from DB if available, else empty list."""
    try:
        from .db_manager import get_recent_logs  # lazy import
        logs = await get_recent_logs(limit)
        return {"logs": logs, "count": len(logs)}
    except Exception:
        return {"logs": [], "count": 0}

REQUEST_COUNT = Counter(
    "apate_requests_total",
    "Total HTTP requests",
    labelnames=("method", "path", "status"),
)
REQUEST_LATENCY = Histogram(
    "apate_request_latency_seconds",
    "Request latency",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

@app.middleware("http")
async def _metrics_middleware(request, call_next):
    method = request.method
    path = request.url.path
    start = datetime.now(UTC)
    try:
        response = await call_next(request)
        status = str(response.status_code)
        return response
    finally:
        duration = (datetime.now(UTC) - start).total_seconds()
        REQUEST_COUNT.labels(method=method, path=path, status=locals().get("status", "500")).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

@app.get("/metrics", include_in_schema=False)
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

# Lifespan events
@app.on_event("startup")
async def _startup():
    try:
        # Lazy import to avoid hard dependency
        from .db_manager import init_database
        await asyncio.wait_for(init_database(), timeout=3.0)
        logger.info("Application startup complete (DB ready or fallback active).")
    except asyncio.TimeoutError:
        logger.warning("DB init timed out; continuing with in-memory fallback.")
    except Exception as e:
        logger.warning(f"DB init error: {e}; continuing with in-memory fallback.")

@app.on_event("shutdown")
async def _shutdown():
    try:
        from .db_manager import cleanup_database
        await asyncio.wait_for(cleanup_database(), timeout=2.0)
        logger.info("Application shutdown complete.")
    except Exception:
        pass

if __name__ == "__main__":
    # Run directly without string import to avoid duplicate imports
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
