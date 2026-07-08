# 🎓 Mirage Developer Onboarding (Chronos Framework)

**Naming convention:** Repository codename is **Apate**. Product/idea name is **Mirage**. Framework implementation name is **Chronos**.

**Program phases:**
- **Phase 1 (6 months):** Core systems and validation (complete)
- **Phase 2 (6 months):** Ubuntu-only AI artifact generation under strict constraints

---

## 0. Five-Minute Explanation (Problem → Solution → Why It Matters) 🧠

### The Core Problem

Most honeypots fail for one reason: **state inconsistency under adversarial interaction**.

Attackers do not just run one command. They run chains of dependent actions and test whether the environment has memory:

1. `touch /tmp/.x`
2. `ls /tmp`
3. `cat /tmp/.x`
4. `stat /tmp/.x`

If any step contradicts a prior step, the deception is exposed. Traditional script-based honeypots often return plausible text, but they do not maintain a coherent filesystem state graph. LLM-only systems improve linguistic realism, but hallucinate state when context windows expire.

**The bottleneck is not language quality — it is transactional truth.**

### The Chronos Solution

Chronos treats deception as a systems problem, not a prompt problem.

- **FUSE-backed interface**: all attacker interactions become real filesystem syscalls.
- **State Hypervisor (Redis + Lua)**: mutations are handled atomically, persisted, and auditable.
- **Artifact Generation (Ollama)**: missing file content is generated locally under strict Ubuntu constraints, then committed to Redis — never re-generated.
- **Audit-first design**: all interactions are captured as structured session events.

The key design move: *generate once, constrain strictly, persist, and reuse consistently.*

### 30-Second Version (for slides)

> Existing honeypots fail when attackers test continuity. Chronos solves continuity at the syscall layer using FUSE + Redis atomic state, then uses a local LLM only to fill missing Ubuntu file content that is immediately persisted. Result: a consistent Ubuntu environment that is easy to validate and hard for attackers to identify as synthetic.

---

## 1. The Big Picture 🌍

**Chronos emulates exactly one system: an Ubuntu server.**

The machine type (web server, database host, development box) is not declared as a "persona" — it is implied by which packages are installed and which services are running. This is defined in `config/ubuntu.yaml`.

Two config files drive the entire AI layer:

| File | Defines |
|---|---|
| `config/ubuntu.yaml` | What the machine **is** (state) — packages, services, users, kernel |
| `config/generation_policy.yaml` | How artifacts are **generated** (behavior) — categories, constraints, model routing |

State and behavior are deliberately kept separate.

---

## 2. The Architecture 🏛️

```
SSH Gateway
    │  generates session_id → injects into threading.local
    ▼
ChronosFUSE  (src/chronos/interface/fuse.py)
    │  every syscall is session-aware via fd-table[fd].session_id
    ▼
State Hypervisor  (src/chronos/core/state.py)
    │  Redis + atomic Lua scripts — sole source of filesystem truth
    │
    ├── cache hit  → return blob immediately (fast path)
    │
    └── cache miss → GenerationOrchestrator
                          │
                          ├── ArtifactPolicyEngine   assigns file class + category
                          ├── PromptBuilder          builds constraint-first prompt
                          ├── InferenceRuntime       sends to local Ollama
                          └── SemanticValidator      validates vs. MachineState
                                    │
                                    └── persists blob + provenance to Redis
```

---

## 3. Directory Map 🗺️

```text
src/chronos/
├── core/                   # State management
│   ├── state.py            # State Hypervisor (Redis + Lua)
│   ├── database.py         # Redis connection
│   └── lua/                # Atomic scripts (atomic_create.lua)
│
├── interface/              # FUSE filesystem
│   └── fuse.py             # Syscall handlers (read/write/mkdir/…)
│
├── intelligence/           # AI generation pipeline
│   ├── ubuntu_profile.py   # Loads config/ubuntu.yaml → MachineState
│   ├── artifact_policy.py  # File class resolution + artifact category sampling
│   ├── prompt_builder.py   # Constraint-first prompt construction
│   ├── validator.py        # 4-tier semantic validation
│   ├── orchestrator.py     # Non-blocking background generation pool
│   └── inference.py        # Ollama HTTP client (local inference only)
│
├── gateway/                # Entry points
│   ├── ssh_server.py       # SSH gateway (injects session_id into FUSE context)
│   └── http_server.py      # HTTP gateway (web app emulation)
│
├── watcher/                # Audit & monitoring
│   ├── log_streamer.py     # Real-time PostgreSQL audit streaming
│   └── event_processor.py  # Pattern-based attack detection
│
├── skills/                 # Threat intelligence (monitoring only, not generation)
│   ├── command_analyzer.py # MITRE ATT&CK detection
│   ├── threat_library.py   # Known attack signatures
│   └── skill_detector.py   # Attacker behavioral profiling
│
└── layer0/                 # Rust performance layer
    └── src/                # Traffic classification, circuit breakers
```

---

## 4. Life of a Command 🔄

### Scenario A: Attacker writes a file

**Command**: `echo "test" > /tmp/pwn`

1. OS calls `create("/tmp/pwn")`.
2. **FUSE** tells **State Hypervisor**: "Create this file".
3. **Hypervisor** runs a **Lua script** in Redis: checks parent, allocates inode, links name → inode.
4. **FUSE** fire-and-forget: submits background generation to `GenerationOrchestrator`.
5. OS calls `write(inode, data)` → FUSE stores the written bytes as a blob.

### Scenario B: Attacker reads a ghost file

**Command**: `cat /etc/nginx/nginx.conf` (inode exists, no content yet)

1. OS calls `read("/etc/nginx/nginx.conf")`.
2. **FUSE** sees the inode has **no content_hash**.
3. **FUSE** calls `orchestrator.get_or_generate(inode, path, session_id, machine_state)`.
4. **ArtifactPolicyEngine** resolves: `config_file`, category `valid`, model `llama3:8b`, max 80 lines.
5. **PromptBuilder** builds a constrained prompt with only nginx-relevant MachineState facts.
6. **InferenceRuntime** sends to local Ollama.
7. **SemanticValidator** checks result against MachineState (nginx version, no mysql references, Ubuntu conventions).
8. Result persisted to Redis. Future reads hit the cache.
9. If Ollama times out → FUSE returns `EAGAIN`. Generation continues in background. Next read hits cache.

---

## 5. Developer Cheatsheet ⌨️

**Start the stack:**
```bash
make up
```

**Watch generation logs:**
```bash
make logs
```

**Connect as attacker:**
```bash
ssh -p 2222 ubuntu@localhost    # any password
```

**Run intelligence verification:**
```bash
PYTHONPATH=src python3 tests/verification/verify_phase3.py
```

**Reset everything:**
```bash
make clean
```

**Edit the Ubuntu machine definition:**
```bash
$EDITOR config/ubuntu.yaml
```

**Edit generation behavior (categories, constraints, model routing):**
```bash
$EDITOR config/generation_policy.yaml
```

---

## 6. Pro Tips 💡

- **State in Lua**: File creation atomicity lives in `src/chronos/core/lua/atomic_create.lua`. Never bypass it.
- **No cloud LLMs**: All inference goes to Ollama on `chronos-net`. There are no OpenAI/Anthropic API keys in this stack.
- **Ubuntu only**: `SemanticValidator` will reject any generated content that references Windows, macOS, or non-Ubuntu package managers (yum, dnf, zypper). This is intentional.
- **Session ≠ Process**: FUSE syscalls are session-aware via `threading.local` — never via `/proc` PID lookups. Session ID is set by the SSH gateway at connection start.
- **Skill detection ≠ generation fidelity**: The `SkillDetector` feeds monitoring and logging. It does **not** change which model generates content — that is determined by file class only.
