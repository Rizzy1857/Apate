# Project Mirage - Technical Foundations & Current Implementation

## 📋 **Overview**

Project Mirage is a multi-service honeypot framework built with enterprise-grade security and realistic deception capabilities. The current implementation provides a solid foundation of core honeypot services with comprehensive logging, monitoring, and security hardening.

## 🎯 **Mission Statement**

Create a production-ready honeypot system that can safely capture and analyze cyber threats while maintaining high levels of deception realism and operational security.

## 🏗️ **Current System Architecture**

Project Mirage implements a **multi-layer service architecture** with the following components:

```text
┌─────────────────────────────────────────────────────────────┐
│                    SECURITY PERIMETER                       │
│          Advanced Firewall + Network Isolation             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              HONEYPOT SERVICES LAYER                │    │
│  │     SSH :2222  |  HTTP :8080  |  IoT :8081          │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │            ORCHESTRATION LAYER               │    │    │
│  │  │          FastAPI Backend :8000               │    │    │
│  │  │  ┌─────────────────────────────────────┐    │    │    │
│  │  │  │         DATA LAYER                  │    │    │    │
│  │  │  │   SQLite DB  |  Redis Cache        │    │    │    │
│  │  │  │  ┌─────────────────────────────┐    │    │    │    │
│  │  │  │  │     PROTOCOL LAYER           │    │    │    │    │
│  │  │  │  │   Rust TCP Server :7878      │    │    │    │    │
│  │  │  │  └─────────────────────────────┘    │    │    │    │
│  │  │  └─────────────────────────────────────┘    │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 🛡️ **Security Architecture**

Project Mirage implements **enterprise-grade security** with military-level isolation for production honeypot deployments:

### Security Layers

- **Network Isolation**: Container subnet isolation (172.20.0.0/16) with strict egress controls
- **Advanced Firewall**: Production iptables with dynamic threat detection and automated response
- **Container Security**: Non-root execution, capability dropping, read-only filesystems, resource limits
- **Secrets Management**: AES-256 encryption with automated rotation (7-90 day cycles)
- **Runtime Monitoring**: Falco runtime security, Wazuh HIDS, Prometheus metrics, Grafana dashboards

*For complete security details, see [Security Implementation Summary](SECURITY_IMPLEMENTATION_SUMMARY.md)*

## 🏛️ **Core Components**

### 1. FastAPI Backend (`backend/app/`)

**Purpose**: Central orchestration and API server  
**Language**: Python 3.13  
**Port**: 8000

#### Key Modules

- **`main.py`**: FastAPI application entry point with health checks and metrics
- **`routes.py`**: REST API endpoints for honeypot management and data access
- **`models.py`**: Pydantic data models for alerts, logs, and interactions
- **`database.py`**: SQLAlchemy ORM for SQLite database operations
- **`config.py`**: Application configuration and environment management

#### Current Features

- RESTful API for honeypot interaction data
- Prometheus metrics integration
- CORS middleware for development
- Health check endpoints
- Session management via Redis
- Comprehensive logging with structured JSON

### 2. SSH Honeypot (`backend/app/honeypot/ssh_emulator.py`)

**Purpose**: Realistic SSH service emulation  
**Language**: Python  
**Port**: 2222

#### Current Implementation

- **Authentication**: Accepts common credential pairs (admin/admin, root/password, etc.)
- **Shell Simulation**: Basic command handling with realistic responses
- **Filesystem Emulation**: Virtual directory structure with fake files
- **Session Logging**: Complete interaction capture with commands and responses
- **Adaptive Responses**: Context-aware command output generation

#### Supported Commands

- Basic Linux commands: `ls`, `pwd`, `cd`, `cat`, `whoami`, `uname`
- System commands: `ps`, `netstat`, `ifconfig`, `top`
- File operations: `touch`, `mkdir`, `rm`
- Network utilities: `ping`, `wget`, `curl`

### 3. HTTP Honeypot (`backend/app/honeypot/http_emulator.py`)

**Purpose**: Web application emulation and form handling  
**Language**: Python  
**Port**: 8080

#### Current Features

- **Login Page Generation**: Adaptive login forms for various services
- **Admin Panel Simulation**: Fake administrative interfaces
- **Banner Generation**: Realistic service banners and error pages
- **Form Processing**: Credential capture and validation simulation
- **Session Management**: User session tracking and persistence

#### Emulated Services

- Router administration interfaces
- Database management tools
- IoT device configuration panels
- Network equipment interfaces
- Application admin dashboards

### 4. Go IoT Services (`go-services/main.go`)

**Purpose**: IoT device endpoint emulation  
**Language**: Go  
**Port**: 8081

#### Current Implementation

```go
type DeviceInfo struct {
    DeviceID     string    `json:"device_id"`
    DeviceType   string    `json:"device_type"`
    Model        string    `json:"model"`
    Firmware     string    `json:"firmware"`
    Status       string    `json:"status"`
    LastSeen     time.Time `json:"last_seen"`
    IPAddress    string    `json:"ip_address"`
    MACAddress   string    `json:"mac_address"`
    Uptime       int64     `json:"uptime_seconds"`
}
```

#### Features

- **Device Discovery**: Fake IoT device enumeration
- **Status Monitoring**: Realistic device health reporting
- **Configuration APIs**: Device parameter management
- **Firmware Simulation**: Version reporting and update endpoints
- **Network Discovery**: Device scanning and identification

### 5. Rust Protocol Server (`rust-protocol/src/main.rs`)

**Purpose**: Layer 0 reflex tagging, triage, and three-lane routing  
**Language**: Rust  
**Port**: 7878

#### Current Implementation

```rust
struct Connection {
    id: String,
    peer_addr: SocketAddr,
    connected_at: DateTime<Utc>,
    bytes_received: u64,
    bytes_sent: u64,
    last_activity: DateTime<Utc>,
}
```

#### Philosophy & Routing Lanes

- **No Dropping**: Layer 0 never drops interesting data in home profile. It observes, tags, responds, and escalates.
- **Tag-and-Route**: Tiny Aho-Corasick core (≤ 20 patterns) and Bloom filter are tagging hints; strategy lives in Layer 1+.
- **Three Lanes**:
  - **Auto**: Known proto + low suspicion → instant fake (FastFake)
  - **Curious**: Odd cadence / unknown proto → delayed fake + escalate (SlowFake)
  - **Suspicious**: Exploit hint / insane rate → immediate escalate (Mirror)

#### Features

- **Protocol Classification**: Byte-prefix detection (SSH, HTTP, FTP, etc.)
- **Verdict Caching**: Cache verdicts only; responses always vary
- **Rate Stats**: Per-IP automation hints (Normal/Bursty/Insane) exposed only to L0 and L3
- **Circuit Breaker**: Work shedding under load; never relaxes security thresholds
- **Async Processing**: High-performance concurrent connections
- **Binary Protocol Support**: Raw TCP data handling

### 6. Data Management

#### SQLite Database (`apate.db`)

**Tables**:
- **alerts**: Security alerts and threat notifications
- **logs**: Honeypot interaction records
- **sessions**: User session tracking
- **honeytokens**: Token deployment and access tracking
- **metrics**: Performance and statistics data

#### Redis Cache (Port 6379)

**Purpose**: Session storage and caching  
**Features**:
- Session persistence across service restarts
- Fast data access for real-time responses
- Distributed caching for multi-instance deployments
- Password protection: `honeypot_redis_2023`

## 🔌 **Integration Points**

### Honeypot Adapter (`backend/app/honeypot/adapter.py`)

**Purpose**: Unified interface for all honeypot services  
**Current State**: Basic structure for future AI integration

```python
class HoneypotAdapter:
    def __init__(self):
        self.ssh_emulator = SSHEmulator()
        self.http_emulator = HTTPEmulator()
    
    async def process_interaction(self, interaction_type, data):
        # Route to appropriate service
        # Log interaction
        # Generate appropriate response
```

### Token Management (`backend/app/honeypot/tokens.py`)

**Purpose**: Honeytoken generation and monitoring  
**Features**:
- Fake credential generation
- API key simulation
- SSH key deployment
- Configuration file templates
- Access detection and alerting

## 📊 **Performance Metrics & Monitoring**

### Core Performance Indicators

- **Mean Time To Discovery (MTTD)**: Current baseline 2-5 minutes → Target 45-60+ minutes
- **False Positive Rate**: Target <5% for production deployments
- **System Resource Usage**: Target <10% CPU, <2GB RAM under normal load
- **Response Time**: <200ms for legitimate requests, variable for suspicious activity
- **Data Collection Rate**: Target 95%+ interaction capture with full context

### Current Monitoring Stack

#### Prometheus Metrics
- HTTP request counters and histograms
- Connection tracking per service
- Error rates and response times
- Resource utilization monitoring

#### Health Checks
- Service availability monitoring
- Database connection status
- Redis connectivity verification
- Cross-service communication validation

## 🐳 **Deployment Architecture**

### Docker Compose Services

The system deploys via Docker Compose with the following services:

```yaml
services:
  backend:          # FastAPI orchestrator
    ports: [8000, 2222, 8080]
  
  rust-protocol:    # TCP server
    ports: [7878, 7879]
  
  go-services:      # IoT emulation
    ports: [8081]
  
  redis:            # Caching layer
    ports: [6379]
```

### Security Hardening

All containers implement:
- **Non-root execution**: User ID 1000:1000
- **Capability dropping**: Minimal Linux capabilities
- **Read-only filesystems**: Where applicable
- **Resource limits**: CPU and memory constraints
- **Network isolation**: Custom bridge network
- **Logging**: Structured JSON with rotation

## 🛠️ **Technical Stack Summary**

| Component | Technology | Purpose | Status |
|-----------|------------|---------|--------|
| Backend API | FastAPI + Python 3.13 | Orchestration | ✅ Complete |
| SSH Honeypot | Python | SSH emulation | ✅ Complete |
| HTTP Honeypot | Python | Web emulation | ✅ Complete |
| IoT Services | Go | Device emulation | ✅ Complete |
| Protocol Layer | Rust | TCP services | ✅ Foundation Complete (Reflex Layer In Progress) |
| Database | SQLite + SQLAlchemy | Data persistence | ✅ Complete |
| Cache | Redis | Session storage | ✅ Complete |
| Security | iptables + Docker | Network hardening | ✅ Complete |
| Monitoring | Prometheus + Grafana | Metrics/dashboards | ✅ Complete |
| Deployment | Docker Compose | Container orchestration | ✅ Complete |

## 🔮 **Future Architecture Preview**

To achieve sub-millisecond latency and high cognitive intelligence, the system is evolving into a **Hybrid Rust-Python Architecture**:

- **Unified State**: Rust will hold the canonical session state in memory.
- **Zero-Copy Access**: Python components will access this state directly via PyO3 without serialization overhead.
- **Smart Proxying**: Rust will handle the "Reflex Layer" (DPI & immediate safety checks) and hand off complex interactions to Python only when necessary.

## 🏁 **Getting Started**

### Quick Start

```bash
# Clone and setup
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# Deploy with security hardening (default)
docker-compose up -d

# Add monitoring stack
docker-compose -f docker-compose.yml -f docker-compose-monitoring.yml up -d

# Check services
docker-compose ps
```

### Service Verification

```bash
# API health check
curl http://localhost:8000/status

# SSH honeypot test
ssh admin@localhost -p 2222

# HTTP honeypot test  
curl http://localhost:8080/admin

# IoT service test
curl http://localhost:8081/api/devices
```

This foundation provides a robust, secure, and extensible platform for honeypot operations with clear pathways for future AI integration and advanced capabilities.