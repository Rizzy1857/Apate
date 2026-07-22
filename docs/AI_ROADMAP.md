# Chronos AI Integration Roadmap (Revised)

**Scope:** Phase 2 of Mirage/Chronos — AI integration that makes one Ubuntu server
exceptionally believable. AI generates plausible artifacts under strict constraints.
It never owns state truth, never learns autonomously, and degrades gracefully.

**Governing principle:**
> Chronos is not an AI-powered operating system. It is a deterministic Ubuntu honeypot
> that uses AI only to generate plausible artifacts under strict constraints. The system
> improves through evidence-based policy updates, not autonomous AI learning.

**Related documents:**
- `AI_ARCHITECTURE.md` — components, data flow, deployment topology
- `AI_LOGIC.md` — algorithms, decision rules, pseudocode

---

## 0. What Was Removed

The following concepts have been **deliberately removed**:

| Removed | Reason |
|---|---|
| Multiple persona YAML files (ubuntu_server, vulnerable_db, iot_device, …) | Ubuntu only. Role implied by installed packages. |
| `LLMProvider` ABC (OpenAI / Anthropic / Mock) | Local Ollama only. Air-gapped stack. |
| Skill-Coupled Fidelity (M2.7) | Attacker skill influences monitoring, not generation |
| Generic "device" or "machine type" concept | Ubuntu machine type only |
| AI learning / feedback into model weights | Policy engine only — model never changes |
| Cloud API keys of any kind | Not applicable |
| A/B Testing (M2.G) | Attackers don't fill out satisfaction surveys. Replaced with operational KPIs. |
| 4-tier storage lifecycle (Hot→Warm→Cold→Archive) | Enterprise architecture syndrome. Simplified to Redis → PostgreSQL → Delete. |
| Complex provenance fields (temperature, top_p, seed, prompt hash, model hash) | Forensic noise. Simplified to: model, file_class, prompt_version, generated_at, validated. |

---

## 1. Guardrails (non-negotiable across all milestones)

1. **State truth never comes from AI.** Filesystem existence, permissions, directory structure, and session state remain 100% Redis/Lua. AI only produces file *content*, once, then it's frozen.
2. **No AI call blocks a syscall indefinitely.** Every generation path has an adaptive timeout and a deterministic fallback.
3. **All generated content is provenance-tagged.** Every blob has metadata: model, file_class, prompt_version, generated_at, validated.
4. **AI fallback must never look like an AI fallback.** Timeouts return POSIX-realistic errors (EAGAIN, ETIMEDOUT, EIO). Fallbacks return realistic minimal static content.
5. **AI restricted to Ubuntu artifacts only.** If content would not plausibly exist on Ubuntu 24.04, the Semantic Validator rejects it.

---

## 2. Completed Milestones

### M2.A — Ubuntu Profile & MachineState ✅

**Goal:** Replace multi-persona system with a single Ubuntu machine definition.

**Completed:**
- Removed `config/personas/*.yaml` entirely
- Created `config/ubuntu.yaml` — packages, services, users, kernel, ports, cron, filesystem layout
- Created `src/chronos/intelligence/ubuntu_profile.py` — typed accessors + Redis MachineState builder per session
- Role is inferred from `installed_packages` + `running_services`, never declared

---

### M2.B — Artifact Policy Engine ✅

**Goal:** Every file gets a realistic policy category *before* AI generation.

**Completed:**
- Created `config/generation_policy.yaml` — file-class-based probability distributions, constraint tables, model routing
- Created `src/chronos/intelligence/artifact_policy.py` — `ArtifactPolicyEngine` + `infer_file_class()`
- File classes: `credential_file`, `config_file`, `log_file`, `history_file`, `notes_file`, `script_file`, `temp_file`
- `empty` category short-circuits before any AI call (returns `b''` immediately)

---

### M2.C — Prompt Builder ✅

**Goal:** AI receives constraints, not creative latitude.

**Completed:**
- Created `src/chronos/intelligence/prompt_builder.py`
- Injects only the *relevant subgraph* of MachineState per file class
- Hard line-length constraint embedded in every prompt
- Filename/path sanitized before interpolation (prompt-injection hardening)

---

### M2.D — Non-Blocking Generation & Adaptive Timeouts ✅

**Goal:** Remove synchronous LLM call from FUSE `read()` hot path.

**Completed:**
- `GenerationOrchestrator` with `ThreadPoolExecutor` background pool
- Redis dedup lock `fs:generating:<inode>` (TTL 30s)
- Adaptive timeout: P95(model latency) + 2.0s safety margin
- Per-session inference quota (token bucket in Redis)
- Timeout → randomized POSIX errors; generation continues in background
- FUSE fd-table extended with session context
- `create()` fires background generation; `readdir()` triggers bounded prewarm

---

### M2.E — Semantic Validator ✅

**Goal:** Reject generated content that contradicts MachineState or violates Ubuntu conventions.

**Completed:**
- 4-tier validation: refusal boilerplate → Ubuntu conventions → MachineState contradictions → density limits
- Retry once on REJECT; fall back to static template on second failure

---

### M2.F — Evidence Collector ✅

**Goal:** Produce deterministic, per-session telemetry with zero AI involvement.

**Completed:**
- `src/chronos/watcher/evidence_collector.py` — hooks into AuditLogStreamer event pipeline
- Per-command enrichment: techniques, risk_score, signatures stored in JSONB
- Skill assessment persisted atomically on session disconnect
- Flush to PostgreSQL `session_evidence` table on session close
- `skill_assessment` JSONB column added to persistence layer

---

## 3. Remaining Milestones (Prioritized)

### Tier 1: Must-Have

#### M2.H — SSH → FUSE Routing (CRITICAL)

**Why Tier 1:** The SSH gateway currently returns hardcoded stub responses. The entire Chronos architecture is bypassed during SSH sessions. This is like building a Ferrari engine and connecting it to bicycle pedals.

**Plan:**
- Route SSH commands through the FUSE-mounted filesystem at `/mnt/honeypot`
- Track CWD per session
- Support core commands: `cd`, `ls`, `cat`, `pwd`, `find`, `stat`, `touch`, `mkdir`, `rm`, `echo >`, `grep`
- Pipe and semicolon chaining
- Error responses matching real Ubuntu behavior

#### M2.J — LLM Circuit Breaker

**Plan:**
- Track per-model failure rate and latency percentile
- Auto-degrade to static templates after N consecutive failures
- Time-based backoff recovery with exponential delay
- No FUSE-level errors visible to attacker during degradation

### Tier 2: Important

#### Entropy Engine (NEW)

Filesystem entropy simulation — makes the filesystem feel alive with gradual log growth, cache churn, and service-realistic patterns.

#### Aging System (NEW)

Realistic `mtime`/`atime`/`ctime` distribution — OS files dated to installation, config to setup, logs to recent activity.

#### Provenance (Simplified from original M2.H)

Track only: model, file_class, prompt_version, generated_at, validated. ~~Removed:~~ temperature, top_p, seed, prompt hash, model hash, persona.

### Tier 3: Later

#### Storage Lifecycle (Simplified from M2.I)

Redis → PostgreSQL → Delete. No 4-tier storage system until Redis memory pressure is measurable.

---

## 4. Attacker-Facing KPIs

These replace the removed A/B testing system. They tell you whether the deception is actually working.

| Metric | Source | Why It Matters |
|---|---|---|
| Average session duration | `session_evidence.duration_seconds` | Measures realism |
| Commands executed per session | `session_evidence.commands` | Interaction depth |
| Unique directories visited | `session_evidence.visited_files` | Exploration behavior |
| Cache miss percentage | Orchestrator | AI workload |
| AI generation latency (P50, P95) | Prometheus | Performance |
| Honeypot detection attempts | CommandAnalyzer | Realism indicator |
| Time before first exploit | Evidence timestamps | Attacker confidence |
| Validator rejection rate | SemanticValidator | Model drift signal |
| MTTD (Mean Time To Detection) | EvidenceCollector | Primary deception quality metric |

---

## 5. Delivery Sequence

```
M2.A Ubuntu Profile & MachineState       Done ✅
M2.B Artifact Policy Engine          Done ✅
M2.C Prompt Builder              Done ✅
M2.D Non-Blocking Orchestrator         Done ✅
M2.E Semantic Validator            Done ✅
M2.F Evidence Collector            Done ✅
──────────────────────────────────────────────────────
M2.H SSH → FUSE Routing            ← Tier 1 (Next)
M2.J Circuit Breaker              ← Tier 1
     Entropy Engine              ← Tier 2
     Aging System               ← Tier 2
     Provenance               ← Tier 2
     Storage Lifecycle (simplified)      ← Tier 3
```

---

## 6. Removed Open Decisions (resolved)

| Decision | Resolution |
|---|---|
| Cloud vs. local inference | **Local Ollama only.** No cloud providers. |
| Multi-persona vs. single profile | **Single `ubuntu.yaml`.** Role from packages. |
| Skill-coupled fidelity | **Removed.** Skill → monitoring only. |
| A/B testing | **Removed.** Replaced with operational KPIs. |
| Storage tiers | **Simplified.** Redis → PostgreSQL → Delete. |
| Provenance fields | **Simplified.** 5 fields, not 8+. |
| FUSE session identity | **Option A: fd-table + threading.local.** No /proc. |

---

*Last updated: July 2026. Reprioritized based on external architecture review — features ranked by impact on attacker deception quality.*
