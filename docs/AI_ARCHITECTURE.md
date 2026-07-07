# Chronos AI Architecture Reference

**Purpose:** Component layout, data flow, deployment topology, and storage
schema for the AI integration described in `AI_ROADMAP.md`, implementing
the decision logic in `AI_LOGIC.md`.

This extends `docs/ARCHITECTURE.md` — it does not replace it. The six-layer
architecture (Gateway → FUSE → State Hypervisor → Cognitive Intelligence →
Analysis → Layer 0) is unchanged; this document zooms into Layer 4
(Cognitive Intelligence) and its new dependencies.

---

## 1. Component Map

```mermaid
graph TD
    subgraph "Layer 2: FUSE Interface"
        Read[read syscall]
        Create[create syscall]
        Readdir[readdir syscall]
    end

    subgraph "New: Generation Orchestration"
        Pool[Background Generation Pool]
        Lock[Redis Dedup Lock<br/>fs:generating:inode]
        CB[LLM Circuit Breaker]
        Fidelity[Fidelity Tier Selector]
        Scheduler[CPU/GPU Model Scheduler]
    end

    subgraph "Layer 4: Cognitive Intelligence (extended)"
        Persona[PersonaEngine]
        PersonaCfg[YAML Persona Configs]
        Facts[MachineState<br/>chronos:machine_state:session_id]
        Router[Model Router]
        Runtime[Inference Runtime]
        Ollama[Ollama Local Models]
    end

    subgraph "New: Quality Gate"
        Validator[Semantic Output Validator]
        Templates[Static Template Fallbacks]
    end

    subgraph "Layer 3: State Hypervisor (unchanged)"
        Redis[(Redis)]
    end

    subgraph "New: Storage Lifecycle"
        BlobMeta[fs:blob_meta:hash]
        ColdStore[(Cold Storage DB / Disk)]
        ArchiveStore[(Archive Store)]
    end

    subgraph "Layer 5: Analysis (existing)"
        SkillDetector[SkillDetector]
        Watcher[AuditLogStreamer]
    end

    Create -->|fire-and-forget| Pool
    Readdir -->|bounded prewarm| Pool
    Read -->|cache-miss, adaptive wait| Pool

    Pool --> Lock
    Pool --> CB
    CB --> Fidelity
    Fidelity --> Scheduler
    Scheduler --> Router
    Fidelity -->|low tier| Templates

    Router --> Runtime
    Runtime --> Ollama

    Persona --> PersonaCfg
    Persona --> Facts
    Fidelity --> Persona

    Runtime --> Validator
    Validator -->|accept| Redis
    Validator -->|reject, retry exhausted| Templates
    Templates --> Redis

    Redis --> BlobMeta
    Redis -.->|age out| ColdStore
    ColdStore -.->|expire| ArchiveStore
    
    SkillDetector -->|skill score| Fidelity
    BlobMeta --> Watcher
```

---

## 2. Deployment Topology

```mermaid
graph LR
    subgraph "chronos-net (bridge, no public egress required)"
        Core[core-engine<br/>FUSE + Hypervisor + Intelligence]
        Redis[(redis-store)]
        DB[(db-store / PostgreSQL)]
        Ollama[ollama<br/>local inference runtime]
    end

    Core --> Redis
    Core --> DB
    Core --> Ollama
```

**Key deployment decision:** `ollama` runs as a sibling container on
`chronos-net`, same pattern as `redis-store`/`db-store`. This ensures the entire stack is air-gapped — no attacker-facing container needs public internet access. Abstractions for external providers (OpenAI, Anthropic) have been removed in favor of a robust local-first **Inference Runtime** and **Model Router**.

**Resource note:** `docker-compose.prod.yml` currently caps `core-engine`
at 2 CPU / 2GB. Ollama needs its own budget, ideally GPU-backed if available.

---

## 3. Storage Lifecycle and Schema Additions

Extends the existing schema in `docs/ARCHITECTURE.md §1`. All new keys are additive.

### Redis Additions

| Key Pattern | Type | Purpose | TTL |
|---|---|---|---|
| `fs:generating:<inode>` | String (lock) | Cross-process generation dedup | 30s |
| `chronos:machine_state:<session_id>` | Hash/JSON | Relational world model (hostname, user, IP, services) | Session lifetime |
| `fs:blob_meta:<hash>` | Hash | Provenance: persona, model, prompt, seed, temp, top_p, generated_at, validated, fidelity | None (persists with blob) |
| `chronos:session:<session_id>:fidelity_tier` | String | Current escalated fidelity tier for the session | Session lifetime |
| `chronos:metrics:llm:*` | Counters/Histograms | Generation latency, timeout count, semantic validation pass/fail | None |

### Storage Tiering

To prevent unbounded storage growth from millions of generated blobs, Chronos implements a storage lifecycle:
1.  **Hot (Memory/Cache):** Frequently accessed files and recently generated dynamic files.
2.  **Warm (Redis):** Standard `fs:blob:<hash>` storage for the active session.
3.  **Cold (Disk / PostgreSQL):** Files that haven't been accessed in a defined period but belong to an active session.
4.  **Archive / Delete:** Files belonging to expired sessions are aged out and deleted to reclaim space.

---

## 4. Sequence: Cache-Miss Read With Adaptive Timeout

```mermaid
sequenceDiagram
    participant Attacker
    participant FUSE as ChronosFUSE.read()
    participant Pool as Background Pool
    participant Lock as Redis Lock
    participant CB as Circuit Breaker
    participant Persona as PersonaEngine
    participant Runtime as Inference Runtime
    participant Validator as Semantic Validator
    participant Redis

    Attacker->>FUSE: cat /etc/ghost.conf
    FUSE->>Redis: check content_hash
    Redis-->>FUSE: none (cache miss)
    FUSE->>Pool: get_or_start_generation(inode, path)
    Pool->>Lock: SET fs:generating:<inode> NX EX 30
    Pool->>CB: check_allow()
    CB-->>Pool: allowed (Closed state)
    Pool->>Persona: generate_content(filename, MachineState)
    Persona->>Runtime: generate(prompt)

    alt completes within Adaptive Timeout (e.g. P95 latency + margin)
        Runtime-->>Persona: content
        Persona-->>Pool: content
        Pool->>Validator: validate_semantically(content, content_type)
        Validator-->>Pool: ACCEPT
        Pool->>Redis: persist blob + inode + blob_meta
        Pool-->>FUSE: content
        FUSE-->>Attacker: file content
    else exceeds Adaptive Timeout
        FUSE-->>Attacker: EAGAIN / ETIMEDOUT / EIO (randomized)
        Note over Pool,Runtime: generation continues in background,<br/>not cancelled
        Runtime-->>Persona: content (later)
        Persona-->>Pool: content
        Pool->>Validator: validate_semantically(content, content_type)
        Pool->>Redis: persist blob + inode + blob_meta
        Note over Redis: next read() for this path<br/>takes the fast cache-hit path
    end
```

---

## 5. Sequence: Predictive Generation on `readdir()`

```mermaid
sequenceDiagram
    participant Attacker
    participant FUSE as ChronosFUSE.readdir()
    participant Redis
    participant Pool as Background Pool

    Attacker->>FUSE: ls /etc
    FUSE->>Redis: ZRANGE fs:dir:<inode>
    Redis-->>FUSE: [file1, file2, ..., fileN]
    loop High Priority (Likely Reads) Children
        FUSE->>Redis: check content_hash for child
        alt no content_hash yet
            FUSE->>Pool: submit_background(generate_and_persist)
            Note over Pool: prioritized via task routing
        end
    end
    FUSE-->>Attacker: directory listing (immediate, unaffected by prewarm)
```

---

## 6. MachineState & Fidelity: Data Ownership

```mermaid
graph TD
    Session[SSH/HTTP Session Start] --> StateInit{chronos:machine_state:session_id exists?}
    StateInit -->|no| CreateState[Create relational graph from persona]
    StateInit -->|yes| ReuseState[Reuse existing MachineState]
    CreateState --> StateStore[(chronos:machine_state:session_id)]
    ReuseState --> StateStore

    CmdAnalysis[CommandAnalyzer / SkillDetector<br/>per command] --> ScoreUpdate[skill_score updated]
    ScoreUpdate --> TierCheck{score crosses threshold?}
    TierCheck -->|yes, upward only| TierStore[(chronos:session:id:fidelity_tier)]
    TierCheck -->|no| TierStore

    StateStore --> Generation[generate_content call via Prompt Builder]
    TierStore --> Generation
    Generation --> Output[Generated content]
```

This makes explicit that **MachineState and fidelity tier are independent axes**:
a low-fidelity session (`template_only`) still uses the same locked relational state if it later escalates. Consistency doesn't reset when fidelity changes, only richness does.

---

## 7. Failure Domain Isolation

```mermaid
graph TD
    subgraph "Always available regardless of AI state"
        StateOps[Filesystem state ops<br/>create, unlink, mkdir, getattr]
        Detection[CommandAnalyzer / ThreatLibrary /<br/>SkillDetector]
        Audit[AuditLogStreamer / EventProcessor]
    end

    subgraph "Degradable"
        Generation[Content generation]
        Fidelity[Fidelity tiering]
    end

    Outage[Inference Runtime outage] -->|circuit breaker trips| Generation
    Generation -->|falls back to| Templates[Static templates]
    Outage -.->|no effect on| StateOps
    Outage -.->|no effect on| Detection
    Outage -.->|no effect on| Audit
```

---

## 8. What This Does *Not* Change

To keep this document scoped correctly:

- **FUSE syscall semantics** (`getattr`, `readdir`, `unlink`, `rmdir`,
  `chmod`, `chown`, `truncate`) are untouched — only `read()` and `create()`
  gain new orchestration logic.
- **Atomic Lua scripts** (`atomic_create.lua`) are untouched — inode
  allocation and directory linking remain exactly as fast and atomic as
  before.
- **Layer 0 (Rust)** is untouched — protocol classification, circuit
  breaking for traffic, and noise detection operate independently of
  anything in this document.
