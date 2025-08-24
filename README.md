# Mirage - Adaptive LLM-Driven Honeypot

An intelligent, next-generation honeypot system that uses Large Language Models (LLMs) to create adaptive, realistic deception environments. Mirage solves the key problems of traditional honeypots: easy detection and low-value logs.

## 📖 **Documentation**

- **[📊 Progress Tracking](progress.md)** - Current development status and roadmap
- **[📚 Usage Guide](usage.md)** - Comprehensive setup and operation guide
- **[🔧 API Reference](usage.md#-api-reference)** - Detailed API documentation
- **[🚀 Quick Start](#-quick-start)** - Get started in 5 minutes

## 📋 **Table of Contents**

- [What Makes Mirage Different](#-what-makes-mirage-different)
- [Quick Start](#-quick-start)
- [Architecture](#️-architecture)
- [Development Setup](#-development-setup)
- [Configuration](#️-configuration)
- [Monitoring & Alerts](#-monitoring--alerts)
- [Testing](#-testing)
- [Security Considerations](#-security-considerations)
- [Customization](#️-customization)
- [Performance Tuning](#-performance-tuning)
- [Project Status](#-project-status)
- [Contributing](#-contributing)

## 🎯 What Makes Mirage Different

### Adaptive Engagement

- **AI-Driven Responses**: Uses LLMs to generate contextual, realistic responses that adapt to attacker behavior
- **Dynamic Environment**: File systems, services, and responses evolve based on attacker actions
- **Behavioral Learning**: Analyzes attacker patterns to improve deception effectiveness

### Advanced Deception

- **Fingerprint Morphing**: Actively changes system signatures to avoid detection
- **Smart Honeytokens**: Context-aware deployment of credentials, API keys, and files
- **Multi-Protocol Support**: SSH, HTTP, TCP, and IoT device emulation

### Intelligence-Focused

- **High-Signal Alerts**: Only triggers on meaningful attacker actions
- **Threat Enrichment**: Automatic correlation with external threat intelligence
- **Behavioral Profiling**: Builds comprehensive attacker profiles over time

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### Services Available

| Service | Port | Description |
|---------|------|-------------|
| FastAPI Backend | 8000 | Main API and orchestration |
| SSH Honeypot | 2222 | Adaptive SSH emulation |
| HTTP Honeypot | 8080 | Web service deception |
| Rust TCP Server | 7878 | Low-level protocol emulation |
| Go IoT Gateway | 8081 | Fake IoT device endpoints |
| Redis Cache | 6379 | Session storage |

### Test the Installation

```bash
# Test main API
curl http://localhost:8000/status

# Test SSH honeypot (API endpoint)
curl -X POST http://localhost:8000/honeypot/ssh/interact \
  -H "Content-Type: application/json" \
  -d '{"command": "ls", "session_id": "test"}'

# Test IoT device
curl http://localhost:8081/camera

# Test TCP echo service
echo "Hello Mirage" | nc localhost 7878
```

## 🏗️ Architecture

```markdown
Mirage Honeypot Ecosystem
├── Backend (Python/FastAPI)
│   ├── SSH Emulator - Realistic command handling
│   ├── HTTP Emulator - Adaptive login pages
│   ├── Honeytoken Generator - Smart bait deployment
│   └── AI Adapter - LLM integration layer
├── AI Engine (Python)
│   ├── Behavior Analysis - Attacker profiling
│   ├── Response Generation - Contextual outputs
│   └── Threat Assessment - Risk scoring
├── Rust Protocol Server
│   ├── TCP Echo Service - Network protocol realism
│   └── Fingerprint Masking - Anti-detection
├── Go IoT Services
│   ├── Camera Endpoints - IoT device simulation
│   └── Configuration APIs - Admin interfaces
└── Data Layer
    ├── Session Storage (Redis)
    ├── Threat Intelligence
    └── Honeytoken Database
```

## 🔧 Development Setup

### Prerequisites

- Python 3.11+
- Rust 1.70+
- Go 1.21+
- Docker & Docker Compose

### Local Development

```bash
# Backend development
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Rust service development
cd rust-protocol
cargo run

# Go service development
cd go-services
go run main.go
```

### VS Code Dev Container

The repository includes a complete dev container setup:

```bash
# Open in VS Code
code .

# Use "Reopen in Container" when prompted
# All tools and dependencies will be automatically available
```

## 🎛️ Configuration

### AI Provider Setup

Mirage supports multiple AI providers:

```bash
# Environment variables
export AI_PROVIDER=openai          # openai, anthropic, local_llm, ollama, stub
export OPENAI_API_KEY=your_key     # For OpenAI
export ANTHROPIC_API_KEY=your_key  # For Anthropic
export LOCAL_LLM_ENDPOINT=http://localhost:8080  # For local models
```

### Honeypot Behavior

```bash
# Customize honeypot behavior
export HONEYPOT_MODE=adaptive      # adaptive, static, aggressive
export THREAT_THRESHOLD=medium     # low, medium, high, critical
export SESSION_TIMEOUT=3600        # Session timeout in seconds
```

## 📊 Monitoring & Alerts

### Real-time Dashboards

- **Main Status**: `http://localhost:8000/status`
- **Active Sessions**: `http://localhost:8000/sessions`
- **Threat Events**: `http://localhost:8000/threats`
- **Honeytokens**: `http://localhost:8000/honeytokens`

### Log Analysis

```bash
# View aggregated logs
docker-compose logs -f backend

# Filter threat events
docker-compose logs backend | grep "THREAT"

# Monitor honeytoken triggers
docker-compose logs backend | grep "HONEYTOKEN"
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Test specific components
python -m pytest tests/test_ssh.py -v
python -m pytest tests/test_http.py -v
python -m pytest tests/test_tokens.py -v
```

## 🚨 Security Considerations

### Isolation

- Run in isolated network segments
- Use containers for service isolation
- Monitor resource usage

### Data Protection

- Honeytokens contain fake data only
- No real credentials or sensitive information
- Regular security audits recommended

### Legal Compliance

- Ensure compliance with local laws
- Document honeypot deployment for legal protection
- Consider privacy implications

## 🛠️ Customization

### Adding New Commands (SSH)

```python
# In backend/app/honeypot/ssh_emulator.py
async def _handle_new_command(self, session: SSHSession, args: List[str]) -> str:
    # Implement new command logic
    return "Command output"

# Register in command_handlers dict
self.command_handlers["newcmd"] = self._handle_new_command
```

### Custom Honeytokens

```python
# In backend/app/honeypot/tokens.py
def generate_custom_token(self, token_type: str) -> Dict[str, str]:
    # Implement custom token generation
    return {
        "token_id": self._generate_token_id(),
        "custom_data": "value"
    }
```

## 📈 Performance Tuning

### Resource Optimization

```yaml
# docker-compose.yml resource limits
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

## 📊 **Project Status**

**Current Completion**: 85% ✅

| Component | Status | Notes |
|-----------|--------|-------|
| 🔧 Core Honeypot Logic | ✅ Complete | SSH/HTTP emulators, honeytokens |
| 🚀 Backend API | ✅ Complete | FastAPI with all endpoints |
| 🦀 Rust Protocol Services | ✅ Complete | TCP services, utilities |
| 🧪 Testing Infrastructure | ✅ Complete | 53 tests, 100% pass rate |
| 🔄 CI/CD Pipeline | ✅ Complete | GitHub Actions, automated testing |
| 🐳 Docker Infrastructure | ✅ Complete | Multi-service deployment |
| 📚 Documentation | 🔄 In Progress | Usage guides, API docs |
| 🤖 AI Engine Integration | ⏳ Planned | OpenAI/Anthropic integration |
| 🏭 Go IoT Services | ⏳ Planned | IoT device simulation |

See **[📊 Progress Tracking](progress.md)** for detailed status and roadmap.

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Run test suite: `python -m pytest`
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Open Pull Request

### Code Standards

- Python: Black formatting, type hints, docstrings
- Rust: Cargo fmt, clippy linting
- Go: gofmt, golint
- All: Comprehensive tests required

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI and Anthropic for LLM APIs
- The cybersecurity research community
- Contributors to honeypot technologies

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Rizzy1857/Apate/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Rizzy1857/Apate/discussions)

---

**⚠️ Disclaimer**: This tool is for research and legitimate cybersecurity purposes only. Users are responsible for compliance with applicable laws and regulations.
