# Usage Guide - Apate Honeypot Platform

## 🚀 **Quick Start**

### Prerequisites

- **Docker & Docker Compose** (recommended)
- **Python 3.11+** (for local development)
- **Rust 1.70+** (for protocol services)
- **PostgreSQL** (for database)

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# For Docker deployment (recommended)
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# For local development
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 2. Verify Installation

```bash
# Test the main API
curl http://localhost:8000/

# Expected response:
{
  "status": "running",
  "service": "Mirage Honeypot",
  "timestamp": "2025-08-24T...",
  "components": {
    "ssh_emulator": "active",
    "http_emulator": "active",
    "ai_engine": "active"
  }
}

# Run the comprehensive smoke test
python docker_smoke_test.py
```

---

## 🏗️ **Deployment Options**

### Option 1: Docker Compose (Production Ready)

```bash
# Production deployment
docker-compose up -d

# Development with database
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Option 2: Local Development

```bash
# Start database services only
docker-compose up -d postgres redis

# Run backend locally
cd backend
uvicorn app.main:app --reload --port 8000

# Run Rust protocol service
cd rust-protocol
cargo run

# Run tests
python -m pytest tests/ -v
```

### Option 3: Individual Service Testing

```bash
# Test SSH emulator
curl -X POST http://localhost:8000/honeypot/ssh/interact \
  -H "Content-Type: application/json" \
  -d '{"command": "ls -la", "session_id": "test_session"}'

# Test HTTP login
curl -X POST http://localhost:8000/honeypot/http/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password", "ip": "192.168.1.100"}'
```

---

## 📚 **API Reference**

### Core Endpoints

#### Health & Status

```http
GET /
GET /status
```

#### SSH Honeypot Interaction

```http
POST /honeypot/ssh/interact
Content-Type: application/json

{
  "command": "ls -la",
  "session_id": "unique_session_id"
}
```

**Response:**

```json
{
  "success": true,
  "output": "total 24\ndrwxr-xr-x 6 admin admin 4096 Aug 24 10:30 .\n...",
  "session_id": "unique_session_id",
  "timestamp": "2025-08-24T10:30:15.123456Z"
}
```

#### HTTP Honeypot Login

```http
POST /honeypot/http/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password123",
  "ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

**Response:**

```json
{
  "success": false,
  "error": "Invalid credentials",
  "server": "Apache/2.4.41 (Ubuntu)",
  "alert_level": "MEDIUM",
  "timestamp": "2025-08-24T10:30:15.123456Z"
}
```

#### Alerts & Logs

```http
GET /alerts?limit=10
GET /logs?limit=50
```

### Advanced API Routes

```http
# Honeypot management (via /api/v1 prefix)
GET /api/v1/honeytokens
POST /api/v1/honeytokens/generate
GET /api/v1/sessions
GET /api/v1/threats
```

---

## 🎛️ **Configuration**

### Environment Variables

#### Core Configuration

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/apate
REDIS_URL=redis://localhost:6379/0

# AI Provider (optional)
AI_PROVIDER=openai          # openai, anthropic, stub
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=ant-your-key

# Honeypot Behavior
HONEYPOT_MODE=adaptive      # adaptive, static, aggressive

# Profiles (planned rollout)
# home:    drop_nothing=true, log_everything=true, latency_budget=relaxed
# enterprise: drop_known_noise=true, sample_benign=true, latency_budget=strict
# These map to routing lanes (auto-respond, curious, suspicious) and will live in Layer 1+ tagging, not Layer 0 drops.
THREAT_THRESHOLD=medium     # low, medium, high, critical
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR
```

#### Docker Environment

```yaml
# docker-compose.override.yml
environment:
  - DATABASE_URL=postgresql://apate_user:apate_dev_password@postgres:5432/apate_dev
  - REDIS_URL=redis://redis:6379/0
  - AI_PROVIDER=stub
  - ENVIRONMENT=development
  - LOG_LEVEL=DEBUG
```

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| FastAPI Backend | 8000 | Main API and web interface |
| SSH Honeypot | 2222 | SSH service simulation |
| HTTP Honeypot | 8080 | Web service simulation |
| Rust TCP Server | 7878 | Low-level protocol simulation |
| Go IoT Services | 8081 | IoT device endpoints |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache and sessions |

---

## 🔧 **Development Guide**

### Setting Up Development Environment

```bash
# 1. Clone and setup
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt
pip install black ruff mypy  # Development tools

# 4. Start development services
docker-compose -f docker-compose.override.yml up -d postgres redis

# 5. Run the application
cd backend
uvicorn app.main:app --reload --port 8000
```

### Code Quality

```bash
# Format code
black backend/ tests/

# Lint code
ruff check backend/ tests/ --fix

# Type checking
mypy backend/app/

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=backend/app --cov-report=html
```

### Adding New Features

#### 1. Adding SSH Commands

```python
# In backend/app/honeypot/ssh_emulator.py

async def _handle_new_command(self, session: SSHSession, args: List[str]) -> str:
    """Handle new command logic"""
    logger.info(f"New command executed by {session.source_ip}")
    return "Command output here"

# Register in __init__ method
self.command_handlers["newcmd"] = self._handle_new_command
```

#### 2. Adding HTTP Endpoints

```python
# In backend/app/honeypot/http_emulator.py

async def handle_new_endpoint(self, path: str, params: dict, source_ip: str) -> dict:
    """Handle new endpoint logic"""
    return {
        "success": True,
        "data": "response data",
        "alert_level": "LOW"
    }
```

#### 3. Adding Honeytoken Types

```python
# In backend/app/honeypot/tokens.py

def generate_custom_token(self, service: str) -> Dict[str, str]:
    """Generate custom honeytoken"""
    token_id = self._generate_token_id()
    return {
        "token_id": token_id,
        "type": "custom_type",
        "data": "custom data",
        "metadata": {"service": service}
    }
```

### Testing New Features

```bash
# Run specific tests
python -m pytest tests/test_ssh.py -v
python -m pytest tests/test_http.py -v
python -m pytest tests/test_tokens.py -v

# Run integration tests
python -m pytest tests/test_honeypot_integration.py -v

# Test API endpoints
python test_integration.py
```

---

## 🚨 **Security Considerations**

### Deployment Security

1. **Network Isolation**: Deploy in isolated network segments
2. **Container Security**: Use non-root users in containers
3. **Secrets Management**: Use environment variables for sensitive data
4. **Monitoring**: Enable comprehensive logging and alerting
5. **Updates**: Keep dependencies updated regularly

### Data Protection

```bash
# Ensure honeytokens contain only fake data
# Rotate credentials regularly
# Monitor for data leakage
# Implement proper access controls
```

### Legal Compliance

- Document honeypot deployment for legal protection
- Ensure compliance with local laws and regulations
- Consider privacy implications and data retention
- Implement proper consent mechanisms if required

---

## 📊 **Monitoring & Observability**

### Health Checks

```bash
# Service health
curl http://localhost:8000/status

# Database connectivity
docker-compose exec postgres pg_isready -U apate_user

# Redis connectivity
docker-compose exec redis redis-cli ping
```

### Log Analysis

```bash
# View application logs
docker-compose logs -f backend

# Filter for specific events
docker-compose logs backend | grep "THREAT"
docker-compose logs backend | grep "HONEYTOKEN"

# Export logs for analysis
docker-compose logs --no-color backend > honeypot.log
```

### Metrics Collection

```bash
# Application metrics (when Prometheus is enabled)
curl http://localhost:8000/metrics

# System metrics
docker stats

# Service status
docker-compose ps
```

---

## 🔍 **Troubleshooting**

### Common Issues

#### Database Connection Failed

```bash
# Check PostgreSQL status
docker-compose exec postgres pg_isready

# Restart database
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

#### Service Won't Start

```bash
# Check all service status
docker-compose ps

# View detailed logs
docker-compose logs service_name

# Rebuild containers
docker-compose up -d --build
```

#### Tests Failing

```bash
# Check Python environment
python --version
pip list

# Run tests with verbose output
python -m pytest tests/ -vv

# Check for import issues
python -c "from backend.app.main import app; print('Import successful')"
```

#### High Resource Usage

```bash
# Monitor container resources
docker stats

# Limit container resources
# Add to docker-compose.yml:
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 512M
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with detailed output
uvicorn app.main:app --reload --log-level debug

# Enable SQL query logging
export DATABASE_DEBUG=true
```

---

## 🚀 **Advanced Usage**

### Custom AI Integration

```python
# Create custom AI provider
class CustomAIProvider:
    async def generate_response(self, context: dict) -> str:
        # Your AI logic here
        return "Custom AI response"

# Register in app configuration
app.ai_provider = CustomAIProvider()
```

### Multi-Tenant Deployment

```yaml
# docker-compose.yml for multiple instances
services:
  honeypot-tenant1:
    extends: backend
    environment:
      - TENANT_ID=tenant1
      - DATABASE_URL=postgresql://user:pass@db/tenant1_db
    
  honeypot-tenant2:
    extends: backend
    environment:
      - TENANT_ID=tenant2
      - DATABASE_URL=postgresql://user:pass@db/tenant2_db
```

### Load Balancing

```yaml
# nginx.conf
upstream honeypot_backend {
    server honeypot1:8000;
    server honeypot2:8000;
    server honeypot3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://honeypot_backend;
    }
}
```

---

## 📝 **Best Practices**

### Development

- Use virtual environments for Python development
- Write tests for all new features
- Follow the existing code style and patterns
- Document new APIs and configuration options
- Use meaningful commit messages

### Operations

- Monitor resource usage and performance
- Implement proper backup strategies
- Use infrastructure as code (IaC) for deployments
- Set up alerting for critical issues
- Plan for disaster recovery

### Security

- Regularly update dependencies
- Scan for vulnerabilities
- Implement proper access controls
- Monitor for suspicious activities
- Maintain audit logs

---

## 🤝 **Contributing**

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `python -m pytest`
5. Check code quality: `ruff check backend/` and `black backend/`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Provide detailed information about the issue
- Include steps to reproduce for bugs
- Add relevant logs and error messages

---

## 📚 **Additional Resources**

- **[Progress Tracking](progress.md)**: Current development status and roadmap
- **[API Documentation](https://github.com/Rizzy1857/Apate/wiki)**: Detailed API reference
- **[Docker Documentation](https://docs.docker.com/)**: Docker and Docker Compose guides
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)**: FastAPI framework reference
- **[PostgreSQL Documentation](https://www.postgresql.org/docs/)**: Database configuration and management

---
*Last Updated: October 24, 2025*

---
## Appendix: Dormant Guardrails Status

Refer to the **[Guardrails Status](GUARDRAILS_STATUS.md)** document for detailed information on the current state and future activation plans of the `household_safety.py` and `privacy.py` modules.

## Appendix: Layer 0 Summary

Refer to the **[Layer 0 Summary](LAYER0_SUMMARY.md)** document for a comprehensive overview of the Layer 0 implementation, including protocol classification, routing logic, and critical reminders for future development and code reviews.