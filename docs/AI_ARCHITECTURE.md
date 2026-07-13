# Chronos AI Architecture Reference

**Purpose:** Component layout, data flow, deployment topology, and storage
schema for the AI integration described in `AI_ROADMAP.md`.

This extends `docs/ARCHITECTURE.md` — it does not replace it. The six-layer
architecture (Gateway → FUSE → State Hypervisor → Cognitive Intelligence →
Analysis → Layer 0) is unchanged; this document zooms into Layer 4
(Cognitive Intelligence) and its dependencies.

**Governing principle:**
> Chronos is not an AI-powered operating system. It is a deterministic Ubuntu honeypot
> that uses AI only to generate plausible artifacts under strict constraints.

---

## 1. Component Map

```mermaid
graph TD
  subgraph "Layer 2: FUSE Interface"
    Read[read syscall]
    Create[create syscall]
    Readdir[readdir syscall]
    FDTable["fd-table entry\n{session_id, inode,\nopen_time, flags, path}"]
  end

  subgraph "Generation Pipeline (Layer 4)"
    Pool[GenerationOrchestrator\nThreadPoolExecutor]
    Lock["Redis Dedup Lock\nfs:generating:<inode> TTL=30s"]
    Policy[ArtifactPolicyEngine\nfile class → category + constraints]
    Builder[PromptBuilder\nconstraint-first Ubuntu prompt]
    Runtime[InferenceRuntime\nOllama HTTP client]
    Ollama[Ollama\nlocal models only]
    Validator[SemanticValidator\n4-tier Ubuntu validation]
    Templates[Static Template Fallbacks\nminimal Ubuntu-plausible content]
  end

  subgraph "Machine Definition"
    UbuntuYAML["config/ubuntu.yaml\n(state)"]
    PolicyYAML["config/generation_policy.yaml\n(behavior)"]
    Profile[UbuntuProfile\ntypes + MachineState builder]
    MachineState["chronos:machine_state:<session_id>\nRedis hash"]
  end

  subgraph "Layer 3: State Hypervisor"
    Redis[(Redis)]
  end

  subgraph "Provenance & Lifecycle"
    BlobMeta["fs:blob_meta:<hash>\nRedis hash"]
    ColdStore[(PostgreSQL)]
  end

  subgraph "Layer 5: Analysis"
    SkillDetector[SkillDetector\nmonitoring only]
    Watcher[AuditLogStreamer]
  end

  Read --> Pool
  Create -->|fire-and-forget| Pool
  Readdir -->|bounded prewarm| Pool
  Read -.->|carries session_id| FDTable

  Pool --> Lock
  Pool --> Policy
  PolicyYAML --> Policy
  Policy --> Builder
  UbuntuYAML --> Profile
  Profile --> MachineState
  MachineState --> Builder
  Builder --> Runtime
  Runtime --> Ollama
  Ollama --> Validator
  MachineState --> Validator
  Validator -->|accept| Redis
  Validator -->|reject x2| Templates
  Templates --> Redis

  Redis --> BlobMeta
  Redis -.->|age out| ColdStore

  SkillDetector -->|detection evidence only| Watcher
  BlobMeta --> Watcher
```

> **Note:** `SkillDetector` feeds monitoring/logging only. It does **not** influence
> which model generates content. Model routing depends solely on file class.

---

## 2. Deployment Topology

```mermaid
graph LR
  subgraph "chronos-net (bridge, no public egress)"
    Core["core-engine\nFUSE + Hypervisor + Intelligence"]
    Redis[(redis-store)]
    DB[(db-store / PostgreSQL)]
    Ollama["ollama\nlocal inference only"]
  end

  Core --> Redis
  Core --> DB
  Core --> Ollama
```

The entire stack is air-gapped. No container requires public internet access.
There are no cloud LLM providers (OpenAI, Anthropic) in this architecture.
All inference is handled by Ollama running as a sibling container on `chronos-net`.

**Resource note:** `ollama` needs its own CPU/memory budget in `docker-compose.prod.yml`.
GPU-backed inference is supported via Docker device passthrough if available.

---

## 3. Storage Schema Additions

All new Redis keys are additive to the existing schema in `docs/ARCHITECTURE.md §1`.

### Redis Additions

| Key Pattern | Type | Purpose | TTL |
|---|---|---|---|
| `fs:generating:<inode>` | String (lock) | Cross-thread generation dedup | 30s |
| `chronos:machine_state:<session_id>` | Hash | Ubuntu machine state per session (packages, services, users, ports, …) | Session lifetime |
| `fs:blob_meta:<hash>` | Hash | Provenance: ubuntu_version, kernel_version, model, file_class, category, generated_at, validated | Persists with blob |
| `chronos:metrics:latency:<model>` | JSON list | Rolling 50-sample latency window for adaptive timeout calculation | None |
| `chronos:quota:<session_id>:<window>` | Integer | Per-session inference quota counter (token bucket) | 2× quota window |

### Storage Tiering

| Tier | Storage | Contents |
|---|---|---|
| Hot | Redis memory | Recently accessed blobs, active session MachineState |
| Warm | Redis persistent | Standard `fs:blob:<hash>` for active sessions |
| Cold | PostgreSQL | Blobs from sessions inactive > threshold |
| Archive/Delete | — | Blobs from expired sessions, aged out |

---

## 4. Sequence: Cache-Miss Read With Adaptive Timeout

```mermaid
sequenceDiagram
  participant Attacker
  participant FUSE as ChronosFUSE.read()
  participant Pool as GenerationOrchestrator
  participant Lock as Redis Lock
  participant Policy as ArtifactPolicyEngine
  participant Builder as PromptBuilder
  participant Runtime as InferenceRuntime
  participant Validator as SemanticValidator
  participant Redis

  Attacker->>FUSE: cat /etc/nginx/nginx.conf
  FUSE->>Redis: check content_hash
  Redis-->>FUSE: none (cache miss)
  FUSE->>Pool: get_or_generate(inode, path, session_id, machine_state)
  Pool->>Lock: SET fs:generating:<inode> NX EX 30
  Pool->>Policy: resolve(filename, path)
  Policy-->>Pool: ArtifactPolicy(class=config_file, category=valid, model=llama3:8b, max_lines=80)
  Pool->>Builder: build(filename, path, machine_state, policy)
  Builder-->>Pool: constrained Ubuntu prompt
  Pool->>Runtime: generate(prompt, system_prompt, model=llama3:8b)
  Runtime->>Ollama: POST /api/generate

  alt Completes within adaptive timeout (P95 latency + 2.0s)
    Ollama-->>Runtime: raw content
    Runtime-->>Pool: raw content
    Pool->>Validator: validate(content, policy, machine_state)
    Validator-->>Pool: ACCEPT
    Pool->>Redis: persist blob + inode + blob_meta
    Pool-->>FUSE: content bytes
    FUSE-->>Attacker: file content
  else Timeout exceeded
    FUSE-->>Attacker: EAGAIN / ETIMEDOUT / EIO (randomized)
    Note over Pool,Ollama: generation continues in background,\nnot cancelled
    Ollama-->>Runtime: content (later)
    Pool->>Validator: validate(...)
    Pool->>Redis: persist blob + inode + blob_meta
    Note over Redis: next read() takes fast cache-hit path
  end
```

---

## 5. Sequence: Predictive Generation on `readdir()`

```mermaid
sequenceDiagram
  participant Attacker
  participant FUSE as ChronosFUSE.readdir()
  participant Redis
  participant Pool as GenerationOrchestrator

  Attacker->>FUSE: ls /etc
  FUSE->>Redis: ZRANGE fs:dir:<inode>
  Redis-->>FUSE: [nginx/, ssh/, fail2ban/, …]
  loop Up to 5 ungenerated children
    FUSE->>Redis: check content_hash for child
    alt no content_hash
      FUSE->>Pool: submit_background(inode, path, session_id, PRIORITY_MEDIUM)
    end
  end
  FUSE-->>Attacker: directory listing (immediate, unaffected by prewarm)
```

---

## 6. MachineState: Data Ownership

```mermaid
graph TD
  SSHConnect[SSH Connection] --> SessionID[Generate session_id\nuuid4]
  SessionID --> CtxInject["threading.local\nfuse_context.session_id"]
  CtxInject --> FUSEOpen["fuse.open()\nfd_table[fd] = {session_id, inode, open_time, flags, path}"]

  FUSEOpen --> StateCheck{"chronos:machine_state\n:session_id exists?"}
  StateCheck -->|no| CreateState[UbuntuProfile.build_machine_state()]
  CreateState --> UbuntuYAML[config/ubuntu.yaml]
  CreateState --> StateStore[(Redis: machine_state hash)]
  StateCheck -->|yes| StateStore

  StateStore --> Generation[PromptBuilder\nextracts relevant subgraph]
  Generation --> Output[Generated Ubuntu artifact]
```

MachineState is created once per session from `ubuntu.yaml` and frozen.
AI cannot modify MachineState — it only reads the relevant subgraph when building prompts.

---

## 7. Failure Domain Isolation

```mermaid
graph TD
  subgraph "Always available"
    StateOps["Filesystem state ops\ncreate, unlink, mkdir, getattr"]
    Detection["CommandAnalyzer / ThreatLibrary\nSkillDetector"]
    Audit["AuditLogStreamer / EventProcessor"]
  end

  subgraph "Gracefully degradable"
    Generation[Content generation]
  end

  Outage[Ollama outage] -->|circuit breaker trips| Generation
  Generation -->|falls back to| Templates[Static minimal Ubuntu content]
  Outage -.->|no effect on| StateOps
  Outage -.->|no effect on| Detection
  Outage -.->|no effect on| Audit
```

---

## 8. What This Does *Not* Change

- **FUSE syscall semantics** (`getattr`, `readdir`, `unlink`, `rmdir`, `chmod`, `chown`, `truncate`) are untouched — only `read()` and `create()` gain orchestration logic.
- **Atomic Lua scripts** (`atomic_create.lua`) are untouched — inode allocation and directory linking remain atomic and fast.
- **Layer 0 (Rust)** is untouched — traffic classification and circuit breaking operate independently.
- **SkillDetector** remains unmodified — its output goes to monitoring only, not to model selection.
