# Mirage (Chronos Framework)

> Repository codename: **Apate**
> 
> Product / idea name: **Mirage**
> 
> Core framework name: **Chronos**

> **Cognitive Deception Infrastructure** 
> *A deterministic Ubuntu honeypot with controlled AI artifact generation*

## Project Lifecycle

- **Phase 1 (6 months):** Core deception platform engineering and validation — **Completed**.
- **Phase 2 (6 months):** AI integration hardening — AI generates plausible Ubuntu artifacts under strict constraints, without owning or modifying system state.

---

## What Chronos Is

Chronos emulates **one thing exceptionally well: an Ubuntu server.**

It is a deterministic deception framework. AI is used only to fill file content in carefully constrained places. Everything else — filesystem state, inode allocation, directory structure, session tracking — is handled deterministically by Redis and Lua scripts, with no AI involvement.

**Governing principle:**
> Chronos is not an AI-powered operating system. It is a deterministic Ubuntu honeypot that uses AI only to generate plausible artifacts under strict constraints. The system improves through evidence-based policy updates, not autonomous AI learning.

---

## The Problem This Solves

**Traditional honeypots** — file operations aren't atomic, attackers detect inconsistencies:
```
Attacker: touch /tmp/pwn && ls /tmp
Honeypot: (file not in listing) → DETECTED AS FAKE
```

**LLM-based honeypots** — hallucinate state when context windows expire:
```
Command: cd /home/ubuntu  → LLM remembers
[50 commands later]
Command: pwd        → LLM forgets → HALLUCINATION → DETECTED
```

**Chronos** — atomic state backed by Redis, AI only fills content:
```
Command: touch /etc/ghost.conf   → Stored in Redis (deterministic)
Command: cat /etc/ghost.conf    → Redis miss → Ollama generates Ubuntu artifact
Command: cat /etc/ghost.conf again → Reads from Redis cache (consistent)
```

---

## Key Features

*  **Ubuntu-Only Emulation**: Emulates a single Ubuntu server with configurable packages, services, users, and kernel. Role is implied by installed software.
*  **State Consistency**: Redis State Hypervisor keeps filesystem operations atomic and persistent. State truth never comes from AI.
*  **FUSE Interface**: Intercepts system calls at the kernel boundary. Supports standard tools (`ls`, `cat`, `rm`, `find`, `grep`) without modification.
*  **Controlled AI Generation**: Artifact Policy Engine assigns every file a category (`valid`, `empty`, `abandoned`, `corrupted`, …) *before* generation. AI fills a defined role, never invents facts.
*  **Constraint-First Prompting**: Prompt Builder injects only relevant MachineState subgraph. AI receives hard limits (max lines, package versions, running services) and cannot contradict them.
*  **Semantic Validation**: Four-tier validator rejects refusal boilerplate, non-Ubuntu content, MachineState contradictions, and density violations before any content is persisted.
*  **Non-Blocking Generation**: GenerationOrchestrator runs inference in a background thread pool. FUSE `read()` never blocks indefinitely — adaptive timeouts return realistic POSIX errors (`EAGAIN`, `ETIMEDOUT`).
*  **Session-Identity Architecture**: Every FUSE syscall carries a session ID injected by the SSH gateway. No `/proc` lookups. Quotas, evidence, and MachineState are all session-keyed.
*  **Real-Time Analysis**: Command analyzer detects attack techniques using MITRE ATT&CK framework patterns.
*  **Forensic Logging**: Complete audit trail in PostgreSQL for incident response and threat hunting.
*  **Layer 0 Routing**: High-performance Rust traffic analysis for initial threat tagging.

---

## Architecture

```
SSH Gateway
  │ (session_id injected via threading.local)
  ▼
FUSE Filesystem (ChronosFUSE)
  │ read() / create() / readdir()
  ▼
State Hypervisor (Redis + Lua)  ← sole source of filesystem truth
  │
  ├─ cache hit → return blob directly
  │
  └─ cache miss → GenerationOrchestrator
             │
             ├─ ArtifactPolicyEngine  (assigns file category)
             ├─ PromptBuilder      (constraint-first prompt)
             ├─ InferenceRuntime    (Ollama local inference)
             └─ SemanticValidator    (validate vs. MachineState)
                  │
                  └─ persist blob + provenance to Redis
```

**Machine definition** (`config/ubuntu.yaml`): what the machine *is* — packages, services, users, ports. 
**Generation behavior** (`config/generation_policy.yaml`): how AI generates artifacts — probability distributions, max lines, model routing, quotas.

These two files are deliberately kept separate (state vs. behavior).

---

## Quick Start

### Prerequisites
*  Docker & Docker Compose
*  No cloud API keys required — inference runs locally via Ollama

### Run the Stack

```bash
git clone https://github.com/Rizzy1857/Apate.git chronos
cd chronos
docker compose up --build -d
```

### Verify Status

```bash
docker compose logs -f core-engine
```

### Interact (Simulate Attack)

```bash
ssh -p 2222 ubuntu@localhost  # any password accepted
```

---

## Testing

### Validation (no infrastructure needed)

```bash
# Core infrastructure integrity
make validate-core

# Real attack simulation (28 commands × 5 scenarios)
make validate-attacks
```

### Verification (unit-level component tests)

```bash
make verify

# Or individually
PYTHONPATH=src python3 tests/verification/verify_phase1.py # State & FUSE
PYTHONPATH=src python3 tests/verification/verify_phase2.py # Persistence & Lua
PYTHONPATH=src python3 tests/verification/verify_phase3.py # Intelligence layer
PYTHONPATH=src python3 tests/verification/verify_phase4.py # Gateway, Watcher, Skills
```

---

## Component Overview

| Component | Purpose | Status |
|-----------|---------|--------|
| State Hypervisor | Redis atomic filesystem state | Complete |
| FUSE Interface | Kernel VFS interception + non-blocking AI integration | Phase 2 |
| UbuntuProfile | Single Ubuntu machine definition from `ubuntu.yaml` | Phase 2 |
| ArtifactPolicyEngine | File-class policy resolution (category + constraints) | Phase 2 |
| PromptBuilder | Constraint-first prompt construction | Phase 2 |
| SemanticValidator | 4-tier validation against MachineState | Phase 2 |
| GenerationOrchestrator | Non-blocking background generation pool | Phase 2 |
| InferenceRuntime | Local Ollama HTTP client | Phase 2 |
| SSH Gateway | Session-aware interactive shell (session_id injected) | Phase 2 |
| HTTP Gateway | Web application emulation | Complete |
| Command Analyzer | MITRE ATT&CK technique detection | Complete |
| Threat Library | Known attack signature database | Complete |
| Skill Detector | Attacker behavioral profiling (monitoring only) | Complete |
| Event Processor | Pattern correlation | Complete |
| Audit Streamer | Real-time event streaming | Complete |
| Layer 0 (Rust) | Traffic analysis | Complete |

---

## Documentation

*  [System Architecture](docs/ARCHITECTURE.md)
*  [AI Architecture](docs/AI_ARCHITECTURE.md)
*  [AI Roadmap](docs/AI_ROADMAP.md)
*  [Mirage Roadmap](docs/ROADMAP.md) - Phase plan, milestones, and delivery criteria
*  [Developer Onboarding](docs/ONBOARDING.md)

## License

MIT License. See [LICENSE](LICENSE) for details.
