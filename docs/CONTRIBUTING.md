# Contributing to Apate Honeypot

Thank you for your interest in contributing to Apate! This document provides guidelines for contributing to this adaptive honeypot platform.

## 📋 **Table of Contents**

- [Code of Conduct](#-code-of-conduct)
- [Getting Started](#-getting-started)
- [Development Setup](#-development-setup)
- [Contributing Guidelines](#-contributing-guidelines)
- [Pull Request Process](#-pull-request-process)
- [Coding Standards](#-coding-standards)
- [Testing Requirements](#-testing-requirements)
- [Documentation](#-documentation)
- [Issue Guidelines](#-issue-guidelines)
- [Security Contributions](#-security-contributions)

## 🤝 **Code of Conduct**

This project adheres to a code of conduct that fosters an inclusive and respectful community:

- **Be respectful** and considerate in all interactions
- **Be collaborative** and help others learn and grow
- **Be patient** with newcomers and those learning
- **Be constructive** in feedback and criticism
- **Respect different perspectives** and experiences

Report any unacceptable behavior to the project maintainers.

## 🚀 **Getting Started**

### Prerequisites

Before contributing, ensure you have:

- **Python 3.11+** installed
- **Docker & Docker Compose** for containerized development
- **Git** for version control
- **Basic understanding** of honeypots and cybersecurity concepts

### Quick Start

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/yourusername/Apate.git
cd Apate

# 3. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 4. Install development dependencies
pip install -r backend/requirements.txt
pip install -r requirements-dev.txt

# 5. Run tests to verify setup
pytest tests/ -v

# 6. Start development environment
docker-compose -f docker-compose.override.yml up -d
```

## 🔧 **Development Setup**

### Local Development Environment

```bash
# Backend development
cd backend
uvicorn app.main:app --reload --port 8000

# Run Rust services
cd rust-protocol
cargo run

# Run Go services
cd go-services
go run main.go

# Database setup
docker-compose up -d postgres redis
```

### Development Tools

Install recommended development tools:

```bash
# Code formatting and linting
pip install black ruff mypy pre-commit

# Testing tools
pip install pytest pytest-cov pytest-asyncio

# Documentation
pip install mkdocs mkdocs-material

# Security scanning
pip install bandit safety detect-secrets
```

### Pre-commit Hooks

Set up pre-commit hooks to ensure code quality:

```bash
pre-commit install

# Test pre-commit hooks
pre-commit run --all-files
```

## 📝 **Contributing Guidelines**

### Types of Contributions

We welcome various types of contributions:

- **🐛 Bug fixes**: Fix issues and improve stability
- **✨ New features**: Add honeypot capabilities or emulators
- **📚 Documentation**: Improve docs, examples, and guides
- **🧪 Tests**: Add or improve test coverage
- **🔧 Infrastructure**: CI/CD, Docker, deployment improvements
- **🔒 Security**: Security enhancements and vulnerability fixes

### Contribution Workflow

1. **Check existing issues** to avoid duplicate work
2. **Create an issue** to discuss major changes
3. **Fork the repository** and create a feature branch
4. **Make your changes** following coding standards
5. **Add tests** for new functionality
6. **Update documentation** as needed
7. **Submit a pull request** with clear description

## 🔄 **Pull Request Process**

### Before Submitting

- [ ] **Code follows** project style guidelines
- [ ] **Tests pass** locally (`python scripts/ci_check.py`)
- [ ] **Coverage maintained** or improved
- [ ] **Documentation updated** for new features
- [ ] **Commit messages** are clear and descriptive
- [ ] **No sensitive data** in commits (API keys, passwords)

### PR Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix/feature causing existing functionality to break)
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Tests added for new functionality
- [ ] Documentation updated
- [ ] No breaking changes without version bump
```

### Review Process

1. **Automated checks** must pass (CI/CD pipeline)
2. **Code review** by maintainers
3. **Testing verification** by reviewers
4. **Documentation review** for completeness
5. **Final approval** and merge

## 🎨 **Coding Standards**

### Python Code Style

Follow PEP 8 with these specifications:

```python
# Line length: 88 characters (Black default)
# Use type hints for all functions
def handle_command(self, command: str, session_id: str) -> str:
    """Process SSH command and return response.
    
    Args:
        command: Command string to execute
        session_id: Unique session identifier
        
    Returns:
        Command output string
        
    Raises:
        CommandError: If command execution fails
    """
    pass

# Use descriptive variable names
ssh_session_manager = SSHSessionManager()
attack_pattern_detected = True

# Document complex logic
def analyze_threat_level(self, session: Session) -> ThreatLevel:
    """Analyze session to determine threat level.
    
    Uses multiple factors including:
    - Command frequency and patterns
    - Failed authentication attempts  
    - Suspicious file access
    - Network reconnaissance activity
    """
    # Implementation here
```

### Rust Code Style

```rust
// Follow rustfmt standards
use std::collections::HashMap;
use tokio::net::TcpListener;

/// Represents a TCP protocol handler
pub struct ProtocolHandler {
    connections: HashMap<String, Connection>,
    threat_detector: ThreatDetector,
}

impl ProtocolHandler {
    /// Creates a new protocol handler
    pub fn new() -> Self {
        Self {
            connections: HashMap::new(),
            threat_detector: ThreatDetector::new(),
        }
    }
    
    /// Handles incoming connections
    pub async fn handle_connection(&mut self, stream: TcpStream) -> Result<(), Error> {
        // Implementation
    }
}
```

### Go Code Style

```go
// Follow gofmt standards
package main

import (
    "context"
    "fmt"
    "net/http"
    "time"
)

// IoTDevice represents an IoT device in the honeypot
type IoTDevice struct {
    ID       string    `json:"id"`
    Type     string    `json:"type"`
    Status   string    `json:"status"`
    LastSeen time.Time `json:"last_seen"`
}

// HandleDeviceRequest processes IoT device requests
func (s *Server) HandleDeviceRequest(w http.ResponseWriter, r *http.Request) {
    // Log the request for threat analysis
    s.logger.Info("IoT device request", 
        "ip", r.RemoteAddr,
        "path", r.URL.Path,
        "user_agent", r.UserAgent(),
    )
    
    // Process request
}
```

## 🧪 **Testing Requirements**

### Test Coverage Standards

- **Minimum coverage**: 85% overall
- **New features**: 90% coverage required
- **Critical paths**: 95% coverage required
- **Security features**: 100% coverage required

### Test Categories

```python
# Unit tests - test individual components
class TestSSHEmulator:
    def test_handle_ls_command(self):
        emulator = SSHEmulator()
        result = emulator.handle_command("ls", "session_123")
        assert "admin" in result
        assert "documents" in result

# Integration tests - test component interaction
class TestHoneypotIntegration:
    async def test_ssh_to_http_session_correlation(self):
        # Test cross-service attack correlation
        pass

# End-to-end tests - test complete workflows
class TestAttackSimulation:
    async def test_full_attack_chain(self):
        # Simulate complete attack scenario
        pass
```

### Test Organization

```
tests/
├── unit/               # Fast, isolated tests
│   ├── test_ssh_emulator.py
│   ├── test_http_emulator.py
│   └── test_ai_engine.py
├── integration/        # Component interaction tests
│   ├── test_api_endpoints.py
│   └── test_database.py
├── e2e/               # End-to-end scenarios
│   ├── test_attack_simulation.py
│   └── test_honeytoken_lifecycle.py
└── fixtures/          # Test data and mocks
    ├── ssh_sessions.json
    └── attack_patterns.json
```

## 📚 **Documentation**

### Documentation Standards

- **API documentation**: Docstrings for all public functions
- **Architecture docs**: High-level system design
- **User guides**: Step-by-step instructions
- **Developer docs**: Setup and contribution guides
- **Security docs**: Threat model and mitigations

### Documentation Format

Use Google-style docstrings:

```python
def generate_honeytoken(self, token_type: str, context: Dict[str, Any]) -> HoneyToken:
    """Generate a new honeytoken for deployment.
    
    Args:
        token_type: Type of token to generate (api_key, credential, etc.)
        context: Additional context for token generation
        
    Returns:
        Generated honeytoken with metadata
        
    Raises:
        TokenGenerationError: If token generation fails
        
    Examples:
        >>> generator = HoneytokenGenerator()
        >>> token = generator.generate_honeytoken("api_key", {"service": "openai"})
        >>> token.token_type
        'api_key'
    """
```

## 🐛 **Issue Guidelines**

### Bug Reports

Use this template for bug reports:

```markdown
**Bug Description**
Clear description of the bug.

**Steps to Reproduce**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**
What should happen.

**Actual Behavior**
What actually happens.

**Environment**
- OS: [e.g., Ubuntu 20.04]
- Python version: [e.g., 3.11.2]
- Docker version: [e.g., 20.10.17]

**Logs**
Relevant log output or error messages.
```

### Feature Requests

Use this template for feature requests:

```markdown
**Feature Description**
Clear description of the proposed feature.

**Use Case**
Why is this feature needed? What problem does it solve?

**Proposed Implementation**
How should this feature work?

**Additional Context**
Any other context, mockups, or examples.
```

## 🔒 **Security Contributions**

### Security Guidelines

- **Never commit real secrets** (API keys, passwords, certificates)
- **Use fake/placeholder values** for honeytokens and examples
- **Follow secure coding practices** (input validation, error handling)
- **Report security issues** privately to maintainers
- **Test security features** thoroughly

### Security Testing

```python
# Example security test
class TestSecurityFeatures:
    def test_input_sanitization(self):
        """Test that malicious input is properly sanitized"""
        malicious_input = "<script>alert('xss')</script>"
        result = sanitize_input(malicious_input)
        assert "<script>" not in result
        
    def test_honeytoken_detection(self):
        """Test that honeytoken access triggers alerts"""
        emulator = HTTPEmulator()
        result = emulator.handle_login("backup_admin", "B@ckup2023!", "1.2.3.4")
        assert result["alert_level"] == "CRITICAL"
        assert result["honeytoken_triggered"] is True
```

## 🏆 **Recognition**

Contributors will be recognized in:

- **README.md** acknowledgments section
- **CHANGELOG.md** for significant contributions
- **GitHub releases** notes for features
- **Project documentation** for major contributions

## 📞 **Getting Help**

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Discord**: Real-time chat with contributors
- **Email**: security@apate-honeypot.com for security issues

## 📋 **Development Checklist**

Before contributing, review this checklist:

### Initial Setup
- [ ] Fork repository and clone locally
- [ ] Set up development environment
- [ ] Install pre-commit hooks
- [ ] Run existing tests successfully
- [ ] Read project documentation

### Development Process
- [ ] Create feature branch from main
- [ ] Write tests for new functionality
- [ ] Implement feature following coding standards
- [ ] Update documentation as needed
- [ ] Run full test suite locally
- [ ] Check code coverage metrics

### Submission Process
- [ ] Review your own code thoroughly
- [ ] Ensure no sensitive data in commits
- [ ] Write clear commit messages
- [ ] Create descriptive pull request
- [ ] Respond to code review feedback
- [ ] Ensure CI/CD pipeline passes

## 🗺️ **Project Roadmap**

Current focus areas for contributions:

### High Priority
- **AI engine improvements**: LLM integration and response quality
- **Performance optimization**: Handling high-volume attacks
- **Security enhancements**: Container security and isolation
- **Documentation**: User guides and API documentation

### Medium Priority
- **Additional protocols**: FTP, SMTP, DNS honeypots
- **Threat intelligence**: External feed integration
- **Monitoring**: Metrics and alerting improvements
- **Mobile support**: Mobile device emulation

### Future Goals
- **Machine learning**: Advanced attack pattern detection
- **Distributed deployment**: Multi-node honeypot clusters
- **Cloud integration**: AWS/Azure/GCP deployment
- **Compliance**: SOC/NIST framework alignment

---

Thank you for contributing to Apate! Your efforts help make the internet safer by advancing honeypot technology and threat detection capabilities.

*Last updated: August 25, 2025*
