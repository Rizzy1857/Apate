# API Documentation

## 📚 **Overview**

The Apate Honeypot Platform provides a comprehensive REST API for managing honeypot services, analyzing threats, and deploying honeytokens. This document covers all available endpoints, request/response formats, and integration examples.

## 🔗 **Base URL**

```
Production: https://your-honeypot.domain.com
Development: http://localhost:8000
Docker: http://localhost:8000
```

## 🔐 **Authentication**

Currently, the API operates in development mode without authentication. For production deployment, implement proper authentication mechanisms.

```bash
# Future authentication header format
Authorization: Bearer <your-api-token>
```

## 📊 **API Overview**

### Core Endpoints

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Health** | `GET /` | Service status |
| **Health** | `GET /status` | Detailed system status |
| **SSH** | `POST /honeypot/ssh/interact` | SSH command simulation |
| **HTTP** | `POST /honeypot/http/login` | HTTP login simulation |
| **Management** | `GET /api/v1/sessions` | Active sessions |
| **Management** | `GET /api/v1/honeytokens` | Honeytoken management |
| **Analytics** | `GET /api/v1/threats` | Threat analysis |
| **Admin** | `POST /api/v1/admin/cleanup` | System maintenance |

## 🏥 **Health & Status Endpoints**

### GET /

Basic health check endpoint.

**Response:**
```json
{
  "status": "running",
  "service": "Mirage Honeypot", 
  "timestamp": "2025-08-25T10:30:15.123456Z",
  "components": {
    "ssh_emulator": "active",
    "http_emulator": "active", 
    "ai_engine": "active"
  }
}
```

### GET /status

Detailed system status information.

**Response:**
```json
{
  "system": "healthy",
  "uptime": "active",
  "honeypots": {
    "ssh": {
      "status": "listening",
      "port": 2222
    },
    "http": {
      "status": "listening", 
      "port": 8080
    },
    "tcp_echo": {
      "status": "listening",
      "port": 7878
    }
  },
  "ai_engine": {
    "status": "ready",
    "model": "adaptive"
  },
  "logging": {
    "status": "active",
    "level": "INFO"
  }
}
```

## 🔒 **Honeypot Interaction Endpoints**

### POST /honeypot/ssh/interact

Simulate SSH command execution.

**Request:**
```json
{
  "command": "ls -la",
  "session_id": "unique_session_id"
}
```

**Response:**
```json
{
  "success": true,
  "output": "total 24\ndrwxr-xr-x 6 admin admin 4096 Aug 24 10:30 .\ndrwxr-xr-x 3 root  root  4096 Aug 24 09:15 ..\n-rw-r--r-- 1 admin admin  220 Aug 24 09:15 .bashrc\ndrwxr-xr-x 2 admin admin 4096 Aug 24 10:30 .ssh\ndrwxr-xr-x 2 admin admin 4096 Aug 24 10:30 documents\n-rw-r--r-- 1 admin admin  157 Aug 24 10:30 credentials.txt",
  "session_id": "unique_session_id",
  "timestamp": "2025-08-25T10:30:15.123456Z"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:8000/honeypot/ssh/interact \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ls -la", 
    "session_id": "test_session_001"
  }'
```

### POST /honeypot/http/login

Simulate HTTP login attempt.

**Request:**
```json
{
  "username": "admin",
  "password": "password123",
  "ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

**Response (Failed Login):**
```json
{
  "success": false,
  "error": "Invalid credentials",
  "server": "Apache/2.4.41 (Ubuntu)",
  "alert_level": "MEDIUM",
  "timestamp": "2025-08-25T10:30:15.123456Z"
}
```

**Response (Honeytoken Triggered):**
```json
{
  "success": true,
  "message": "Login successful",
  "session_token": "ht_abc123def456",
  "redirect_url": "/dashboard",
  "user_role": "admin",
  "server": "Apache/2.4.41 (Ubuntu)",
  "alert_level": "CRITICAL",
  "honeytoken_triggered": true,
  "timestamp": "2025-08-25T10:30:15.123456Z"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:8000/honeypot/http/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password123", 
    "ip": "192.168.1.100"
  }'
```

## 📈 **Management Endpoints**

### GET /api/v1/sessions

Retrieve active honeypot sessions.

**Query Parameters:**
- `limit` (int, optional): Maximum number of sessions to return (default: 50, max: 100)

**Response:**
```json
[
  {
    "session_key": "192.168.1.100_session_001",
    "session_type": "ssh",
    "source_ip": "192.168.1.100", 
    "start_time": "2025-08-25T10:00:00Z",
    "activity_count": 15,
    "ai_enhanced": true
  },
  {
    "session_key": "192.168.1.101_session_002",
    "session_type": "http",
    "source_ip": "192.168.1.101",
    "start_time": "2025-08-25T10:15:00Z", 
    "activity_count": 8,
    "ai_enhanced": false
  }
]
```

### GET /api/v1/sessions/{session_id}

Get detailed information about a specific session.

**Response:**
```json
{
  "session_id": "session_001",
  "source_ip": "192.168.1.100",
  "session_type": "ssh",
  "start_time": "2025-08-25T10:00:00Z",
  "last_activity": "2025-08-25T10:30:00Z",
  "commands_executed": [
    "ls -la",
    "pwd", 
    "cat credentials.txt",
    "whoami"
  ],
  "threat_indicators": [
    "reconnaissance",
    "file_access"
  ],
  "ai_responses": 12,
  "alert_level": "MEDIUM"
}
```

## 🎯 **Honeytoken Management**

### GET /api/v1/honeytokens

Retrieve honeytokens.

**Query Parameters:**
- `active_only` (bool, default: true): Return only active tokens
- `limit` (int, default: 50, max: 100): Maximum tokens to return

**Response:**
```json
{
  "total_count": 25,
  "tokens": [
    {
      "token_id": "ht_api_001",
      "token_type": "api_key",
      "created_at": "2025-08-25T09:00:00Z",
      "is_active": true,
      "trigger_count": 0
    },
    {
      "token_id": "ht_cred_001", 
      "token_type": "credential",
      "created_at": "2025-08-25T09:15:00Z",
      "is_active": true,
      "trigger_count": 2
    }
  ]
}
```

### POST /api/v1/honeytokens/deploy

Deploy new honeytokens.

**Request:**
```json
{
  "token_type": "api_key",
  "count": 3,
  "context": {
    "service": "openai",
    "environment": "production"
  }
}
```

**Response:**
```json
{
  "success": true,
  "deployed_count": 3,
  "tokens": [
    {
      "token_id": "ht_api_123",
      "token_type": "api_key", 
      "token_data": {
        "key": "sk-HONEYTOKEN-FAKE-1234567890abcdef",
        "service": "openai"
      },
      "deployment_location": "/home/admin/.env"
    }
  ]
}
```

**Supported Token Types:**
- `credentials`: Username/password pairs
- `api_key`: API keys for various services
- `ssh_key`: SSH private/public key pairs
- `config`: Configuration files with secrets
- `web_beacon`: Web-based callback tokens

### GET /api/v1/honeytokens/triggered

Get triggered honeytokens.

**Response:**
```json
{
  "triggered_count": 5,
  "tokens": [
    {
      "token_id": "ht_cred_001",
      "token_type": "credential",
      "triggered_at": "2025-08-25T10:25:00Z",
      "trigger_source_ip": "192.168.1.100",
      "trigger_context": {
        "service": "ssh",
        "command": "cat credentials.txt"
      }
    }
  ]
}
```

## ⚠️ **Threat Analysis**

### GET /api/v1/threats

Get threat events.

**Query Parameters:**
- `severity` (string, optional): Filter by severity (low, medium, high, critical)
- `last_hours` (int, default: 24): Hours to look back (1-168)
- `limit` (int, default: 100, max: 500): Maximum events

**Response:**
```json
{
  "total_events": 156,
  "events": [
    {
      "event_id": "threat_1692975015",
      "timestamp": "2025-08-25T10:30:15Z",
      "source_ip": "192.168.1.100",
      "event_type": "brute_force_attempt",
      "description": "Multiple failed login attempts detected",
      "severity": "medium",
      "component": "http_honeypot",
      "metadata": {
        "attempts": 15,
        "timespan": "5 minutes",
        "usernames_tried": ["admin", "root", "administrator"]
      }
    }
  ]
}
```

## 📊 **Analytics Endpoints**

### GET /api/v1/analytics/attackers

Get attacker analytics.

**Response:**
```json
{
  "total_unique_attackers": 42,
  "active_sessions": 8,
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
  "honeytokens_triggered": 5,
  "time_range": "last_24_hours"
}
```

### GET /api/v1/analytics/interactions

Get interaction analytics.

**Response:**
```json
{
  "total_interactions": 342,
  "by_service": {
    "ssh": 234,
    "http": 98,
    "tcp": 8,
    "iot": 2
  },
  "top_commands": [
    {"command": "ls", "count": 156},
    {"command": "pwd", "count": 89},
    {"command": "whoami", "count": 67},
    {"command": "cat", "count": 45},
    {"command": "ps", "count": 34}
  ],
  "ai_enhanced_responses": 187
}
```

## 🔧 **Administrative Endpoints**

### GET /api/v1/admin/health

Comprehensive health check.

**Response:**
```json
{
  "overall_status": "healthy",
  "timestamp": "2025-08-25T10:30:15Z",
  "components": {
    "ssh_emulator": {
      "status": "healthy",
      "active_sessions": 5
    },
    "http_emulator": {
      "status": "healthy", 
      "active_sessions": 3
    },
    "ai_engine": {
      "status": "healthy",
      "provider": "stub"
    },
    "honeytoken_generator": {
      "status": "healthy",
      "active_tokens": 25
    }
  },
  "performance": {
    "memory_usage": "45%",
    "cpu_usage": "12%",
    "disk_usage": "23%"
  }
}
```

### POST /api/v1/admin/cleanup

Clean up old data.

**Request:**
```json
{
  "max_age_days": 30
}
```

**Response:**
```json
{
  "success": true,
  "cleaned_items": {
    "honeytokens": 12,
    "sessions": 45,
    "logs": 1250
  }
}
```

## 📄 **Error Responses**

### Standard Error Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "session_id",
      "issue": "Required field missing"
    }
  },
  "timestamp": "2025-08-25T10:30:15Z",
  "request_id": "req_abc123def456"
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

## 🚀 **Rate Limiting**

Current rate limits (will be implemented in production):

| Endpoint Category | Rate Limit | Window |
|-------------------|------------|--------|
| Health checks | 60 requests | 1 minute |
| Honeypot interactions | 100 requests | 1 minute |
| Management APIs | 30 requests | 1 minute |
| Analytics | 20 requests | 1 minute |
| Admin operations | 10 requests | 1 minute |

**Rate Limit Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1692975075
```

## 📱 **SDK Examples**

### Python SDK Example

```python
import requests
import json

class ApateClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        
    def simulate_ssh_command(self, command, session_id):
        """Simulate SSH command execution"""
        response = requests.post(
            f"{self.base_url}/honeypot/ssh/interact",
            json={"command": command, "session_id": session_id}
        )
        return response.json()
        
    def get_threats(self, severity=None, hours=24):
        """Get threat events"""
        params = {"last_hours": hours}
        if severity:
            params["severity"] = severity
            
        response = requests.get(
            f"{self.base_url}/api/v1/threats",
            params=params
        )
        return response.json()

# Usage example
client = ApateClient()
result = client.simulate_ssh_command("ls -la", "test_session")
print(f"Command output: {result['output']}")
```

### JavaScript/Node.js Example

```javascript
class ApateClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async simulateHttpLogin(username, password, ip) {
        const response = await fetch(`${this.baseUrl}/honeypot/http/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username,
                password,
                ip
            })
        });
        
        return await response.json();
    }
    
    async getActiveSessions(limit = 50) {
        const response = await fetch(
            `${this.baseUrl}/api/v1/sessions?limit=${limit}`
        );
        return await response.json();
    }
}

// Usage
const client = new ApateClient();
client.simulateHttpLogin('admin', 'password', '192.168.1.100')
    .then(result => console.log('Login result:', result));
```

### Bash/cURL Examples

```bash
#!/bin/bash

# Set base URL
BASE_URL="http://localhost:8000"

# Function to simulate SSH command
simulate_ssh() {
    local command="$1"
    local session_id="$2"
    
    curl -s -X POST "$BASE_URL/honeypot/ssh/interact" \
        -H "Content-Type: application/json" \
        -d "{\"command\": \"$command\", \"session_id\": \"$session_id\"}" | \
        jq -r '.output'
}

# Function to get system status
get_status() {
    curl -s "$BASE_URL/status" | jq .
}

# Function to deploy honeytokens
deploy_honeytokens() {
    local token_type="$1"
    local count="$2"
    
    curl -s -X POST "$BASE_URL/api/v1/honeytokens/deploy" \
        -H "Content-Type: application/json" \
        -d "{\"token_type\": \"$token_type\", \"count\": $count}"
}

# Examples
simulate_ssh "ls -la" "bash_session_001"
get_status
deploy_honeytokens "api_key" 3
```

## 🔗 **WebSocket Endpoints** (Future)

Real-time event streaming (planned feature):

```javascript
// Connect to real-time threat feed
const ws = new WebSocket('ws://localhost:8000/ws/threats');

ws.onmessage = (event) => {
    const threatEvent = JSON.parse(event.data);
    console.log('New threat:', threatEvent);
};

// Subscribe to specific event types
ws.send(JSON.stringify({
    action: 'subscribe',
    events: ['honeytoken_triggered', 'brute_force_attempt']
}));
```

## 📚 **OpenAPI Specification**

The complete OpenAPI/Swagger specification is available at:

- **Interactive docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **JSON spec**: `http://localhost:8000/openapi.json`

## 🔍 **Testing the API**

### Health Check Test

```bash
curl -f http://localhost:8000/ || echo "API is down"
```

### Full API Test Script

```bash
#!/bin/bash
set -e

echo "Testing Apate Honeypot API..."

# Test health endpoint
echo "✓ Testing health endpoint..."
curl -s http://localhost:8000/ | jq -e '.status == "running"'

# Test SSH interaction
echo "✓ Testing SSH interaction..."
curl -s -X POST http://localhost:8000/honeypot/ssh/interact \
    -H "Content-Type: application/json" \
    -d '{"command": "whoami", "session_id": "test"}' | \
    jq -e '.success == true'

# Test HTTP login
echo "✓ Testing HTTP login..."
curl -s -X POST http://localhost:8000/honeypot/http/login \
    -H "Content-Type: application/json" \
    -d '{"username": "test", "password": "test", "ip": "127.0.0.1"}' | \
    jq -e '.success == false'

echo "All tests passed! 🎉"
```

---

**API Version**: 1.0  
**Last Updated**: August 25, 2025  
**Support**: Submit issues on GitHub or contact the development team
