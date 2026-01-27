"""
OpenAPI Documentation Configuration for Apate Honeypot API

This module contains the comprehensive API documentation setup including
endpoint descriptions, examples, and interactive Swagger UI configuration.
"""

from typing import Dict, Any, List

# OpenAPI Configuration
OPENAPI_CONFIG = {
    "title": "Apate Honeypot API",
    "description": """
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

### Response Codes
* **200**: Successful operation
* **400**: Bad request - Invalid input parameters
* **404**: Resource not found
* **429**: Rate limit exceeded
* **500**: Internal server error

### Data Models
All API responses follow consistent JSON formatting with standardized error handling.
    """,
    "version": "1.0.0",
    "contact": {
        "name": "Apate Development Team",
        "url": "https://github.com/Rizzy1857/Apate",
        "email": "support@apate-honeypot.dev",
    },
    "license_info": {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    "servers": [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.apate-honeypot.dev", 
            "description": "Production server"
        }
    ]
}

# API Tags for Organization
API_TAGS = [
    {
        "name": "health",
        "description": "Health check and system status endpoints",
        "externalDocs": {
            "description": "System Health Documentation",
            "url": "https://github.com/Rizzy1857/Apate/docs/health"
        }
    },
    {
        "name": "honeypot",
        "description": "Core honeypot interaction endpoints",
        "externalDocs": {
            "description": "Honeypot Documentation", 
            "url": "https://github.com/Rizzy1857/Apate/docs/honeypot"
        }
    },
    {
        "name": "ssh",
        "description": "SSH emulator endpoints for shell simulation",
        "externalDocs": {
            "description": "SSH Emulator Guide",
            "url": "https://github.com/Rizzy1857/Apate/docs/ssh"
        }
    },
    {
        "name": "http", 
        "description": "HTTP emulator endpoints for web service simulation",
        "externalDocs": {
            "description": "HTTP Emulator Guide",
            "url": "https://github.com/Rizzy1857/Apate/docs/http"
        }
    },
    {
        "name": "honeytokens",
        "description": "Honeytoken management and tracking endpoints",
        "externalDocs": {
            "description": "Honeytoken Documentation",
            "url": "https://github.com/Rizzy1857/Apate/docs/honeytokens"
        }
    },
    {
        "name": "analytics",
        "description": "Threat analysis and reporting endpoints",
        "externalDocs": {
            "description": "Analytics Documentation", 
            "url": "https://github.com/Rizzy1857/Apate/docs/analytics"
        }
    }
]

# Endpoint Examples and Documentation
ENDPOINT_DOCS = {
    "/health": {
        "summary": "System Health Check",
        "description": """
        Returns the current health status of all Apate services including:
        - API server status
        - Database connectivity
        - Redis cache status
        - Service dependencies
        """,
        "responses": {
            200: {
                "description": "System is healthy",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "healthy",
                            "timestamp": "2024-12-24T10:30:00Z",
                            "services": {
                                "api": "healthy",
                                "database": "healthy", 
                                "redis": "healthy"
                            },
                            "version": "1.0.0"
                        }
                    }
                }
            }
        }
    },
    "/honeypot/ssh/interact": {
        "summary": "SSH Honeypot Interaction",
        "description": """
        Simulates SSH shell interaction with realistic command responses.
        Supports 15+ common Unix commands with proper filesystem simulation.
        """,
        "request_body": {
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "ssh_session_123",
                        "command": "ls -la",
                        "client_ip": "192.168.1.100"
                    }
                }
            }
        },
        "responses": {
            200: {
                "description": "Command executed successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "output": "drwxr-xr-x 3 user user 4096 Dec 24 10:30 .\ndrwxr-xr-x 5 user user 4096 Dec 24 10:25 ..\n-rw-r--r-- 1 user user  220 Dec 24 10:30 .profile",
                            "threat_level": "LOW",
                            "session_id": "ssh_session_123",
                            "timestamp": "2024-12-24T10:30:00Z"
                        }
                    }
                }
            }
        }
    },
    "/honeypot/http/login": {
        "summary": "HTTP Login Simulation", 
        "description": """
        Simulates various web login interfaces including admin panels, 
        webmail, FTP, and router interfaces with realistic responses.
        """,
        "request_body": {
            "content": {
                "application/json": {
                    "example": {
                        "username": "admin",
                        "password": "password123",
                        "service_type": "admin_panel",
                        "client_ip": "192.168.1.100"
                    }
                }
            }
        },
        "responses": {
            200: {
                "description": "Login attempt processed",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "message": "Invalid credentials",
                            "threat_level": "MEDIUM",
                            "attempt_count": 3,
                            "timestamp": "2024-12-24T10:30:00Z"
                        }
                    }
                }
            }
        }
    }
}

# Security Schemes
SECURITY_SCHEMES = {
    "APIKeyHeader": {
        "type": "apiKey",
        "in": "header", 
        "name": "X-API-Key",
        "description": "API key for production authentication"
    },
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT token authentication"
    }
}

# Common Response Models
RESPONSE_MODELS = {
    "ErrorResponse": {
        "type": "object",
        "properties": {
            "error": {
                "type": "string",
                "description": "Error message"
            },
            "code": {
                "type": "integer", 
                "description": "Error code"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "Error timestamp"
            }
        }
    },
    "HealthResponse": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["healthy", "degraded", "unhealthy"]
            },
            "services": {
                "type": "object",
                "properties": {
                    "api": {"type": "string"},
                    "database": {"type": "string"},
                    "redis": {"type": "string"}
                }
            },
            "version": {
                "type": "string"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time"
            }
        }
    }
}