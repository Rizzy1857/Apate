# Mirage (Chronos Framework) — Implementation Status

**Date:** July 2026  
**Status:**  Phase 1 Complete |  Phase 2 In Progress (M2.A–M2.E complete)

---

## Project Framing

- Repository codename: **Apate**
- Product / idea: **Mirage**
- Core framework: **Chronos**
- Delivery model: two 6-month phases
  - **Phase 1:** Core platform engineering and validation (**Complete**)
  - **Phase 2:** Ubuntu-only AI artifact generation under strict constraints (**In Progress**)

---

##  Completed Components

### Phase 1: Foundation (State Management)
- **State Hypervisor** (`src/chronos/core/state.py`)
  - Filesystem state consistency management
  - Atomic operations via Redis Lua scripts
  - Inode allocation and path resolution
  
- **Database Layer** (`src/chronos/core/database.py`)
  - Redis connection management
  - Schema initialization
  
- **Persistence** (`src/chronos/core/persistence.py`)
  - Audit logging to PostgreSQL
  - Session tracking
  
- **Data Models** (`src/chronos/core/models.py`)
  - Pydantic models for type safety

### Phase 1: FUSE Interface
- **FUSE Filesystem** (`src/chronos/interface/fuse.py`)
  - POSIX syscall implementation
  - Path resolution and inode management
  - File descriptor tracking
  - Integration with State Hypervisor

### Phase 1: Gateway, Watcher & Skills

#### Gateway (Entry Points)
- **SSH Gateway** (`src/chronos/gateway/ssh_server.py`)
  - SSH server implementation using Paramiko
  - Accepts any credentials (deception behavior)
  - Command logging and session tracking
  - Session ID injection into FUSE context via threading.local (Phase 2 update)
  
- **HTTP Gateway** (`src/chronos/gateway/http_server.py`)
  - Simulates vulnerable web application
  - Multiple endpoints (login, admin, API)
  - SQL injection, XSS, directory traversal detection

#### Watcher (Audit & Monitoring)
- **Log Streamer** (`src/chronos/watcher/log_streamer.py`)
  - Real-time PostgreSQL audit log streaming
  - Pub-sub pattern for event distribution
  - Session activity tracking
  
- **Event Processor** (`src/chronos/watcher/event_processor.py`)
  - Pattern-based attack detection
  - Behavioral analysis
  - Risk scoring and classification

#### Skills (Threat Intelligence — monitoring only, not generation)
- **Command Analyzer** (`src/chronos/skills/command_analyzer.py`)
  - MITRE ATT&CK framework mapping
  - Attack pattern detection
  - Risk scoring algorithm
  
- **Threat Library** (`src/chronos/skills/threat_library.py`)
  - Known attack signatures
  - Severity classification
  
- **Skill Detector** (`src/chronos/skills/skill_detector.py`)
  - Attacker behavioral profiling
  - Attack phase progression tracking
  - **Note:** Skill assessment feeds monitoring/logging only — it does NOT influence content generation fidelity

### Layer 0 (Rust)
- **Protocol Analysis** (`src/chronos/layer0/`)
  - Traffic classification
  - Circuit breaker patterns
  - Python bindings via PyO3

---

##  Phase 2: Ubuntu-Only AI Integration (In Progress)

### Completed Milestones

#### M2.A — Ubuntu Profile & MachineState 
- Removed multi-persona YAML system
- Created `config/ubuntu.yaml` — single Ubuntu machine definition (packages, services, users, kernel)
- Created `src/chronos/intelligence/ubuntu_profile.py` — typed accessors + Redis MachineState builder
- Role is implied by installed packages, never declared as a persona type

#### M2.B — Artifact Policy Engine 
- Created `config/generation_policy.yaml` — file-class-based probability distributions, constraints, model routing
- Created `src/chronos/intelligence/artifact_policy.py` — resolves policy per file before generation
- File classes: `credential_file`, `config_file`, `log_file`, `history_file`, `notes_file`, `script_file`, `temp_file`
- Categories: `valid`, `empty`, `abandoned`, `corrupted`, `deprecated`, `active`, `archived`, …
- `empty` category skips AI entirely and returns `b''` immediately

#### M2.C — Prompt Builder 
- Created `src/chronos/intelligence/prompt_builder.py`
- Constraint-first prompts: AI receives hard limits, relevant MachineState subgraph, category instructions
- Sanitizes filenames/paths before interpolation (prompt-injection hardening)
- AI cannot invent facts not present in the Constraints block

#### M2.D — Non-Blocking Generation 
- Created `src/chronos/intelligence/orchestrator.py`
- ThreadPoolExecutor background pool, Redis dedup lock (`fs:generating:<inode>` TTL 30s)
- Adaptive timeout: P95 latency per model + 2.0s safety margin
- Per-session inference quota (token bucket in Redis, keyed by session_id)
- On timeout: randomized POSIX error (EAGAIN/ETIMEDOUT/EIO), generation continues in background
- FUSE fd-table extended to `{session_id, inode, open_time, flags, path}`
- `create()` fires background generation; `readdir()` triggers bounded prewarm

#### M2.E — Semantic Validator 
- Created `src/chronos/intelligence/validator.py`
- Tier 1: Refusal boilerplate detection (markdown fences, "As an AI…", "Here is…")
- Tier 2: Ubuntu convention checks (no Windows, PowerShell, yum, dnf, zypper)
- Tier 3: MachineState contradiction detection (uninstalled package references)
- Tier 4: Information density limits (max_lines enforcement)
- Retry once on REJECT; fall back to static template on second failure

### Upcoming Milestones
- **M2.F** Evidence Collector — deterministic per-session telemetry
- **M2.G** Policy Engine & A/B Testing — evidence-driven policy evolution
- **M2.H** Provenance & SSH FUSE Routing — full command routing through FUSE
- **M2.I** Storage Lifecycle — Hot → Warm → Cold tiering
- **M2.J** Circuit Breaker — graceful Ollama degradation

---

##  Test Coverage

### Verification Scripts (`tests/verification/`)
-  `verify_phase1.py` — State Hypervisor & Database
-  `verify_phase2.py` — FUSE Interface
-  `verify_phase3.py` — Intelligence layer (Ubuntu-only: UbuntuProfile, ArtifactPolicyEngine, PromptBuilder, SemanticValidator)
-  `verify_phase4.py` — Gateway, Watcher, Skills (4/4 tests passing)

### Validation Scripts (`tests/validation/`)
-  `validate_core.py` — Core infrastructure integrity (8/8 tests passing)
-  `test_real_attack.py` — Real attack simulation (78.6% detection rate)

---

##  Project Structure

```
Apate/
├── src/chronos/
│   ├── core/               State management, database, audit logging
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── persistence.py
│   │   ├── state.py
│   │   └── lua/
│   │       └── atomic_create.lua
│   │
│   ├── interface/          FUSE filesystem (Phase 2 updated)
│   │   └── fuse.py
│   │
│   ├── intelligence/       Ubuntu-only AI generation pipeline
│   │   ├── ubuntu_profile.py    ← loads config/ubuntu.yaml
│   │   ├── artifact_policy.py   ← file-class policy resolution
│   │   ├── prompt_builder.py    ← constraint-first prompts
│   │   ├── validator.py         ← 4-tier semantic validation
│   │   ├── orchestrator.py      ← non-blocking background generation
│   │   └── inference.py         ← local Ollama client
│   │
│   ├── gateway/            SSH/HTTP entry points
│   │   ├── ssh_server.py        ← session_id injection (Phase 2)
│   │   └── http_server.py
│   │
│   ├── watcher/            Audit log monitoring
│   │   ├── log_streamer.py
│   │   └── event_processor.py
│   │
│   ├── skills/             Threat detection (monitoring, not generation)
│   │   ├── command_analyzer.py
│   │   ├── threat_library.py
│   │   └── skill_detector.py
│   │
│   └── layer0/             Rust performance layer
│
├── config/
│   ├── ubuntu.yaml              ← Ubuntu machine definition (state)
│   ├── generation_policy.yaml   ← AI generation behavior (behavior)
│   └── prometheus/
│       └── prometheus.yml
│
├── tests/
│   ├── validation/
│   ├── verification/
│   └── integration/
│
├── docs/
│   ├── AI_ARCHITECTURE.md
│   ├── AI_ROADMAP.md
│   ├── ARCHITECTURE.md
│   ├── ONBOARDING.md
│   └── STATUS.md (this file)
│
├── requirements.txt
├── Makefile
├── docker-compose.yml
├── docker-compose.prod.yml
└── Dockerfile
```

---

##  Dependencies

### Python (requirements.txt)
- fusepy==3.0.1 (FUSE interface)
- redis==5.0.1 (state storage)
- psycopg2-binary==2.9.9 (audit logs)
- paramiko==3.4.0 (SSH gateway)
- pydantic==2.5.3 (data models)
- PyYAML==6.0.1 (config loading)
- requests==2.31.0 (Ollama HTTP client)
- prometheus-client (metrics)

### Rust (Layer 0)
- tokio (async runtime)
- serde (serialization)
- pyo3 (Python bindings)
- aho-corasick (pattern matching)

### Infrastructure
- **Redis 7.0+** — state, blobs, quotas, latency metrics
- **PostgreSQL 14+** — audit logs, evidence records
- **Ollama** — local LLM inference (llama3:3b, llama3:8b)

---

##  Hardware Requirements

- **CPU**: 4+ cores recommended (Ollama inference)
- **Memory**: 8GB minimum (16GB recommended for llama3:8b)
- **Storage**: 20GB free space (Ollama model weights + Docker images)
- **OS**: Linux (Ubuntu 20.04+), macOS (for development only), or Windows with WSL2 (for development only)

---

*Last Updated: July 2026 — Phase 2 M2.A–M2.E complete*
