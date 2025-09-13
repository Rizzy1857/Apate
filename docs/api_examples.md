# API Documentation Examples

This directory contains example requests and responses for the Apate Honeypot API.

## Quick Start

1. **Health Check**
```bash
curl -X GET "http://localhost:8000/health"
```

2. **SSH Interaction**
```bash
curl -X POST "http://localhost:8000/honeypot/ssh/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ssh_session_123",
    "command": "ls -la",
    "client_ip": "192.168.1.100"
  }'
```

3. **HTTP Login Simulation**
```bash
curl -X POST "http://localhost:8000/honeypot/http/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password123", 
    "service_type": "admin_panel",
    "client_ip": "192.168.1.100"
  }'
```

## Available Endpoints

### Health & Status
- `GET /health` - System health check
- `GET /status` - Detailed system status

### SSH Honeypot
- `POST /honeypot/ssh/interact` - Execute SSH commands
- `GET /honeypot/ssh/sessions` - List active sessions
- `DELETE /honeypot/ssh/sessions/{session_id}` - Terminate session

### HTTP Honeypot  
- `POST /honeypot/http/login` - Simulate login attempts
- `GET /honeypot/http/templates` - List available templates
- `POST /honeypot/http/beacon` - Track beacon access

### Honeytokens
- `POST /honeytokens/generate` - Generate new honeytokens
- `GET /honeytokens/list` - List deployed tokens
- `POST /honeytokens/trigger` - Record token access

### Analytics
- `GET /analytics/threats` - Threat analysis data
- `GET /analytics/sessions` - Session statistics
- `GET /analytics/alerts` - Security alerts

## Interactive Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Authentication

Development mode runs without authentication. Production deployments should use:
- API Key authentication via `X-API-Key` header
- JWT Bearer tokens for user sessions

## Rate Limiting

Default limits:
- 100 requests per minute per IP
- 1000 requests per hour per IP
- Burst limit: 10 requests per second

## Error Handling

All errors return standardized JSON:
```json
{
  "error": "Description of the error",
  "code": 400,
  "timestamp": "2024-12-24T10:30:00Z"
}
```

## Support

- **Documentation**: https://github.com/Rizzy1857/Apate/docs
- **Issues**: https://github.com/Rizzy1857/Apate/issues
- **Discussions**: https://github.com/Rizzy1857/Apate/discussions