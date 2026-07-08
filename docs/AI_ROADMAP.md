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

The following concepts from the original roadmap have been **deliberately removed**:

| Removed | Reason |
|---|---|
| Multiple persona YAML files (ubuntu_server, vulnerable_db, iot_device, …) | Ubuntu only. Role implied by installed packages. |
| `LLMProvider` ABC (OpenAI / Anthropic / Mock) | Local Ollama only. Air-gapped stack. |
| Skill-Coupled Fidelity (M2.7) | Attacker skill influences monitoring, not generation |
| Generic "device" or "machine type" concept | Ubuntu machine type only |
| AI learning / feedback into model weights | Policy engine only — model never changes |
| Cloud API keys of any kind | Not applicable |

---

## 1. Guardrails (non-negotiable across all milestones)

1. **State truth never comes from AI.** Filesystem existence, permissions, directory structure, and session state remain 100% Redis/Lua. AI only produces file *content*, once, then it's frozen.
2. **No AI call blocks a syscall indefinitely.** Every generation path has an adaptive timeout and a deterministic fallback.
3. **All generated content is provenance-tagged.** Every blob has metadata: ubuntu_version, kernel_version, model, prompt_version, entropy_category, generated_at, validated.
4. **AI fallback must never look like an AI fallback.** Timeouts return POSIX-realistic errors (EAGAIN, ETIMEDOUT, EIO). Fallbacks return realistic minimal static content.
5. **AI restricted to Ubuntu artifacts only.** If content would not plausibly exist on Ubuntu 24.04, the Semantic Validator rejects it.

---

## 2. Milestones

### M2.A — Ubuntu Profile & MachineState  Complete

**Goal:** Replace multi-persona system with a single Ubuntu machine definition.

**Completed:**
- Removed `config/personas/*.yaml` entirely
- Created `config/ubuntu.yaml` — packages, services, users, kernel, ports, cron, filesystem layout
- Created `src/chronos/intelligence/ubuntu_profile.py` — typed accessors + Redis MachineState builder per session
- Role is inferred from `installed_packages` + `running_services`, never declared

**Exit criteria met:** Single ubuntu.yaml drives all MachineState; zero multi-persona code remains.

---

### M2.B — Artifact Policy Engine  Complete

**Goal:** Every file gets a realistic policy category *before* AI generation.

**Completed:**
- Created `config/generation_policy.yaml` — file-class-based probability distributions, constraint tables, model routing, prewarm priorities, inference quotas
- Created `src/chronos/intelligence/artifact_policy.py` — `ArtifactPolicyEngine` + `infer_file_class()`
- File classes: `credential_file`, `config_file`, `log_file`, `history_file`, `notes_file`, `script_file`, `temp_file`
- `empty` category short-circuits before any AI call (returns `b''` immediately)
- Attacker skill level does NOT influence model routing — reproducibility over fidelity tuning

**Exit criteria met:** Every file resolves a class + category + model + constraints before generation begins.

---

### M2.C — Prompt Builder  Complete

**Goal:** AI receives constraints, not creative latitude.

**Completed:**
- Created `src/chronos/intelligence/prompt_builder.py`
- Injects only the *relevant subgraph* of MachineState per file class (e.g., nginx.conf gets nginx_version + open_ports, not cron_jobs)
- Hard line-length constraint embedded in every prompt
- Filename/path sanitized before interpolation (prompt-injection hardening)
- System prompt scopes model to Ubuntu {version} only; explicitly excludes other OS

**Exit criteria met:** Prompt always contains CONSTRAINTS, MACHINE STATE, and OUTPUT blocks; cannot generate content for non-Ubuntu systems.

---

### M2.D — Non-Blocking Generation & Adaptive Timeouts  Complete

**Goal:** Remove synchronous LLM call from FUSE `read()` hot path.

**Completed:**
- Created `src/chronos/intelligence/orchestrator.py` — `GenerationOrchestrator`
- `ThreadPoolExecutor` background pool (8 workers)
- Redis dedup lock `fs:generating:<inode>` (TTL 30s)
- Adaptive timeout: P95(model latency) + 2.0s safety margin, rolling 50-sample window
- Per-session inference quota: token bucket in Redis, keyed by `session_id` (not PID)
- Timeout → randomized `EAGAIN / ETIMEDOUT / EIO`; generation continues in background
- FUSE fd-table extended: `{session_id, inode, open_time, flags, path}`
- SSH gateway injects `session_id` via `threading.local` — no `/proc` lookups
- `create()` fires background generation (HIGH priority)
- `readdir()` triggers bounded prewarm for ungenerated children (MEDIUM priority, limit 5)
- Prometheus metrics: `chronos_generation_latency_seconds`, quota exhaustion counter, timeout counter

**Exit criteria met:** `read()` never blocks longer than adaptive timeout; retry serves cached content; quotas enforced per session.

---

### M2.E — Semantic Validator  Complete

**Goal:** Reject generated content that contradicts MachineState or violates Ubuntu conventions.

**Completed:**
- Created `src/chronos/intelligence/validator.py` — `SemanticValidator`
- Tier 1: Refusal boilerplate (markdown fences, "As an AI…", "Here is…", "I cannot…")
- Tier 2: Ubuntu convention checks (Windows, PowerShell, yum, dnf, zypper)
- Tier 3: MachineState contradiction detection (package references for uninstalled software)
- Tier 4: Information density limits (max_lines enforcement)
- Retry once on REJECT; fall back to static minimal template on second failure

**Exit criteria met:** 100% of generation paths pass through validator; mysql/apache2 contradictions rejected; Windows content rejected.

---

### M2.F — Evidence Collector (Next)

**Goal:** Produce deterministic, per-session telemetry with zero AI involvement.

**Plan:**
- Create `src/chronos/watcher/evidence_collector.py`
- Hook into existing `AuditLogStreamer` event pipeline
- Track: session_id, duration, commands[], visited_files[], traversal_graph, detection_status, detection_confidence, exit_reason, first_suspicious_command, last_successful_interaction
- All fields are deterministic facts — no AI involved
- Flush complete record to PostgreSQL on session close

---

### M2.G — Policy Engine & A/B Testing

**Goal:** Evidence drives policy updates, not intuition. Model never changes.

**Plan:**
- Create `src/chronos/policy/policy_engine.py` — aggregates evidence buckets; surfaces candidate policy updates when N independent sessions exhibit the same pattern
- Create `src/chronos/policy/ab_comparator.py` — compares MTTD, median TTD, detection reason, traversal depth between policy versions
- Candidate policies written as staged files, never hot-deployed automatically
- MTTD tracked together with: median TTD, detection reason, detection command, files inspected before detection, traversal depth

---

### M2.H — Provenance & SSH FUSE Routing

**Goal:** Every blob is auditable; SSH exercises the full FUSE pipeline.

**Plan:**
- `fs:blob_meta:<hash>` fields: ubuntu_version, kernel_version, model, file_class, category, validation_strictness, generated_at, validated
- Route SSH command execution fully through `ChronosFUSE` (replacing stub)
- Surface provenance in `AuditLogStreamer` events

---

### M2.I — Storage Lifecycle

**Goal:** Prevent unbounded blob growth over long deployments.

**Plan:**
- Hot (Redis memory) → Warm (Redis persist) → Cold (PostgreSQL) → Archive/Delete
- Blobs aged out on session expiry
- Dynamic files (logs, histories) stored as appendable versioned blobs
- Config files frozen after first generation

---

### M2.J — LLM Circuit Breaker

**Goal:** Degrade gracefully under Ollama failures.

**Plan:**
- Track per-model failure rate and latency percentile
- Auto-degrade to static templates after N consecutive failures
- Time-based backoff recovery with exponential delay
- No FUSE-level errors visible to attacker during degradation

---

## 3. Delivery Sequence

```
M2.A Ubuntu Profile & MachineState         Done
M2.B Artifact Policy Engine                Done
M2.C Prompt Builder                        Done
M2.D Non-Blocking Orchestrator             Done
M2.E Semantic Validator                    Done
─────────────────────────────────────────────────
M2.F Evidence Collector                   ← Next
M2.G Policy Engine & A/B Testing
M2.H Provenance & SSH FUSE Routing
M2.I Storage Lifecycle
M2.J Circuit Breaker
```

---

## 4. Metrics to Track

| Metric | Source | Target |
|---|---|---|
| Generation timeout rate | Orchestrator | < 5% of cache-misses |
| Inference quota exhaustion rate | Orchestrator | Track per session |
| Validator rejection rate | Validator | Track (signal of model drift) |
| Prewarm hit-rate | FUSE readdir() | > 60% of reads served pre-generated |
| MTTD (Mean Time To Detection) | Evidence Collector | Improve with each policy update |
| Provenance coverage | Orchestrator | 100% of generated blobs |
| Storage eviction rate | Storage lifecycle | Equal to ingestion rate at capacity |

---

## 5. Removed Open Decisions (resolved)

| Decision | Resolution |
|---|---|
| Cloud vs. local inference | **Local Ollama only.** No cloud providers. |
| Multi-persona vs. single profile | **Single `ubuntu.yaml`.** Role from packages. |
| Skill-coupled fidelity | **Removed.** Skill → monitoring only. |
| Entropy probabilities location | **`generation_policy.yaml`** (behavior separate from state). |
| FUSE session identity | **Option A: fd-table + threading.local.** No /proc. |

---

*Last updated: July 2026. This roadmap reflects the revised architecture after the design review.*
