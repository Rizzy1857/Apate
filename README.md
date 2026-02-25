# Chronos Framework

> **Cognitive Deception Infrastructure**  
> *From Theoretical Specification to Deployable Asset*

Chronos is a high-fidelity honeypot framework that solves **state hallucination** and **consistency issues** plaguing both traditional rule-based and LLM-based honeypots. It implements a fully consistent **FUSE Filesystem** backed by a **Redis State Hypervisor**, allowing attackers to interact with it exactly like a real Linux system while Chronos tracks and analyzes every action.

### The Problem This Solves

**Traditional honeypots** suffer from limited interaction - file operations aren't atomic, so attackers detect inconsistencies:
```
Attacker: touch /tmp/pwn && ls /tmp
Honeypot: (file not in listing) → DETECTED AS FAKE
```

**LLM-based honeypots** maintain conversation context but hallucinate state:
```
Command: cd /home/attacker → LLM remembers
[50 commands later]
Command: pwd → LLM forgets (context window exceeded) → HALLUCINATION
```

**Chronos** provides true atomic state management backed by Redis:
```
Command: cd /home/attacker → Stored in Redis
[50 commands later]
Command: pwd → Reads from Redis → CORRECT every time
```

For deep analysis, see [Problem Analysis](docs/PROBLEM_ANALYSIS.md).

## 🚀 Key Features

*   **State Consistency**: A "State Hypervisor" ensures filesystem operations are atomic and persistent. If an attacker creates a file, it stays there. No more disappearing artifacts.
*   **FUSE Interface**: Intercepts system calls at the kernel-user boundary. Supports standard tools (`ls`, `cat`, `rm`, `vi`, `gcc`) without modification.
*   **Cognitive Intelligence**: Integrated **Persona Engine** generates content for files on-the-fly using LLMs (OpenAI/Anthropic) only when accessed, creating an infinite, realistic depth.
*   **Multi-Protocol Gateway**: SSH and HTTP honeypot servers that capture credentials and exploitation attempts.
*   **Real-Time Analysis**: Command analyzer detects attack techniques using MITRE ATT&CK framework patterns.
*   **Threat Intelligence**: Built-in library of known attack signatures and threat patterns.
*   **Skill Profiling**: Automatically classifies attacker skill level from script kiddie to expert APT.
*   **Audit Streaming**: Real-time event processing and pattern detection across attack sessions.
*   **Layer 0 Routing**: High-performance Rust-based traffic analysis for initial threat tagging.
*   **Forensic Logging**: Complete audit trail in PostgreSQL for incident response and threat hunting.

## 🏗️ Architecture

Chronos implements a layered architecture:

1.  **Gateway Layer (Entry Points)**:
    *   **SSH Honeypot**: Accepts any credentials, provides interactive shell on port 2222
    *   **HTTP Honeypot**: Simulates vulnerable web apps, captures exploits on port 8080
    *   All entry points log to the audit system for analysis
    
2.  **Core Layer (State & Logic)**:
    *   **State Hypervisor**: Ensures filesystem consistency via Redis atomic operations
    *   **FUSE Interface**: Intercepts kernel VFS calls, translates to database operations
    *   **Hot State**: Redis 7.0 for sub-millisecond metadata access
    *   **Cold Storage**: PostgreSQL 15 for forensic audit logs

3.  **Intelligence Layer (Cognitive)**:
    *   **Persona Engine**: Injects realistic personality into generated content
    *   **LLM Integration**: OpenAI/Anthropic/Mock providers for lazy content generation
    *   Generates files on first access, persists forever (consistency guarantee)

4.  **Analysis Layer (Skills & Watcher)**:
    *   **Command Analyzer**: Detects 50+ attack techniques (MITRE ATT&CK)
    *   **Threat Library**: Database of known attack signatures and IOCs
    *   **Skill Detector**: Profiles attacker from script kiddie → expert APT
    *   **Event Processor**: Real-time pattern detection and correlation
    *   **Audit Streamer**: Pub-sub event streaming for external SIEM integration

5.  **Layer 0 (Rust Performance)**:
    *   High-speed protocol classification and noise filtering
    *   Circuit breakers and adaptive degradation under load
    *   Direct integration with Python via PyO3

## ⚡ Quick Start

### Prerequisites
*   Docker & Docker Compose
*   (Optional) OpenAI/Anthropic API Key for intelligence features

### Run the Stack

1.  **Clone & Build**:
    ```bash
    git clone https://github.com/Rizzy1857/Apate.git chronos
    cd chronos
    docker compose up --build -d
    ```

2.  **Verify Status**:
    ```bash
    docker compose logs -f core-engine
    ```

3.  **Interact (Simulate Attack)**:
    Enter the container to experience the FUSE filesystem:
    ```bash
    docker exec -it chronos_core /bin/bash
    cd /mnt/honeypot
    
## 🧪 Verification & Testing

### Phase 1 Status: Implementation Complete, Validation Required ⚠️

**What's Built:**
- ✅ Complete architecture with all components implemented
- ✅ Redis-backed state management with atomic operations
- ✅ FUSE filesystem with full POSIX support
- ✅ SSH and HTTP honeypot gateways
- ✅ Threat detection and attacker profiling
- ✅ Audit logging and event streaming

**What's NOT Proven:**
- ❌ State consistency under concurrent load (not tested)
- ❌ Real attack resilience (zero real-world tests)
- ❌ Performance under stress (no benchmarks)
- ❌ Crash recovery (not tested)
- ❌ Comparison with existing solutions like Cowrie

**Reality Check:**
This is a technically sound architecture that *should* work as designed, but Phase 1 requires **proving it works**, not just implementing it.

See [Phase 1 Validation](docs/PHASE1_VALIDATION.md) for honest assessment and testing roadmap.

### Run Core Validation

Test fundamental system integrity (no hype):

```bash
# Start infrastructure
make up

# Run brutal honesty validation
make validate-core
```

This tests:
- Redis connectivity and atomic operations
- State persistence and consistency
- Lua script execution
- Directory simulation
- Performance baselines

### Run Implementation Tests

Run verification tests to confirm component functionality:

```bash
# Run all verification phases
make verify

# Or individually
python3 verify_phase1.py  # Core: State & FUSE
python3 verify_phase2.py  # Persistence & Lua
python3 verify_phase3.py  # Intelligence & Persona
python3 verify_phase4.py  # Gateway, Watcher, Skills
```

### Run Demo

Run the interactive demo:

```bash
# Standalone demo (no infrastructure needed)
python3 demo_standalone.py
```

This simulates a complete APT attack session and shows:
- Real-time command analysis
- Threat signature matching
- Attacker skill profiling
- Attack phase detection
- Risk scoring and reporting

## 📊 Component Overview

| Component | Purpose | Status |
|-----------|---------|--------|
| State Hypervisor | Filesystem consistency engine | ✅ Complete |
| FUSE Interface | Kernel VFS interception | ✅ Complete |
| Persona Engine | Content generation AI | ✅ Complete |
| SSH Gateway | Interactive shell honeypot | ✅ Complete |
| HTTP Gateway | Web app honeypot | ✅ Complete |
| Command Analyzer | Attack technique detection | ✅ Complete |
| Threat Library | Signature database (12 threats) | ✅ Complete |
| Skill Detector | Attacker profiling | ✅ Complete |
| Event Processor | Pattern correlation | ✅ Complete |
| Audit Streamer | Real-time event streaming | ✅ Complete |
| Layer 0 (Rust) | Traffic analysis | ✅ Complete |

## 📚 Documentation

*   [System Architecture](docs/ARCHITECTURE.md) - Deep dive into technical design
*   [Developer Onboarding](docs/ONBOARDING.md) - Get started contributing

## 📜 License

## 🛠️ Configuration

Environment variables in `docker-compose.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Hostname of Redis service | `redis-store` |
| `POSTGRES_HOST` | Hostname of Postgres service | `db-store` |
| `LLM_PROVIDER` | `openai`, `anthropic`, or `mock` | `mock` |
| `OPENAI_API_KEY` | Key for OpenAI (if used) | - |

## 📚 Documentation

*   [System Architecture](docs/ARCHITECTURE.md)
*   [Developer Guide](docs/DEVELOPMENT.md) (Coming Soon)

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
