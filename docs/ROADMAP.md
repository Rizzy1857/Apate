# Mirage Roadmap (Apate Repository)

This roadmap defines the delivery plan for **Mirage** (product idea) implemented via the **Chronos** framework in the **Apate** repository.

## Naming Rules

- Repository codename: **Apate**
- Product/idea name: **Mirage**
- Framework/engine name: **Chronos**

## Core Design Thesis

> AI doesn't own truth. Redis owns truth. AI fills empty spaces.

Chronos is a deterministic Ubuntu honeypot that uses AI only to generate plausible file content under strict constraints. The system improves through evidence-based policy updates, not autonomous AI learning.

## Program Structure

Mirage is delivered in two phases, with remaining work prioritized by **impact on attacker deception quality**:

- **Phase 1 (6 months): Core platform engineering + validation** — **Completed**
- **Phase 2 (6 months): AI integration for realism without complexity** — **In Progress**

---

## Evidence Base Used for This Roadmap

This roadmap is grounded in repository state and commit history, not speculative targets.

### Commit-Derived Milestones (Selected)

| Date | Commit | Milestone Evidence |
|------|--------|---------------------|
| 2025-08-24 | `a2fce5e`, `a9b7dca` | Initial structure and core files in Apate |
| 2025-11-21 | `30ca497`, `bba4434` | Python FFI + hybrid Rust/Python architecture documented |
| 2025-11-25 | `8938ae3`, `90eb90e` | Circuit breaker + Layer 0 threat detection integration |
| 2025-12-21 | `e8066ce`, `7e6571b` | Layer 0/1 integration and scoring/correlation work |
| 2026-02-09 | `071682e`, `e7168e6` | Production compose, monitoring, Phase 4 (gateway/watcher/skills) |
| 2026-02-25 | `0820809` | Phase 1 validation docs and scripts |
| 2026-03-02 | `6180396` | Validation targets, docs updates, test reorganization |
| 2026-07-22 | — | Overseer GUI (egui), evidence enrichment, skill persistence |

### Current Verified Baseline

From repository docs and tests as of July 2026:

- Core state engine + atomic Redis/Lua operations
- FUSE interface and filesystem simulation
- SSH/HTTP gateways (SSH currently stub shell — see Tier 1)
- Skills stack (command analyzer, threat library, skill detector)
- Watcher stack (event processor, log streamer, evidence collector)
- Layer 0 Rust performance subsystem
- Overseer Dashboard (egui — Live Ops, Sessions, Session Detail)
- AI generation pipeline (M2.A–M2.F complete)
- Validation coverage including core checks and attack simulation

---

## Priority Framework

Remaining work is prioritized by a single question: **does this increase the odds that an attacker believes they're on a real machine?**

Features that directly improve deception quality come first. Infrastructure polish comes after the illusion has been validated.

---

## Tier 1: Must-Have (Critical Path)

These are blocking. Without them, the deception doesn't work end-to-end.

### SSH → FUSE Routing (M2.H)

**Why it's Tier 1:** The SSH gateway currently returns hardcoded stub responses. Attackers aren't touching the FUSE filesystem at all. This means the entire Chronos architecture — State Hypervisor, lazy generation, semantic validation — is bypassed during SSH sessions.

**Scope:**
- Route SSH commands through the FUSE-mounted filesystem at `/mnt/honeypot`
- Track CWD per session
- Support: `cd`, `ls`, `cat`, `pwd`, `find`, `stat`, `touch`, `mkdir`, `rm`, `echo >`, `grep`
- Pipe and semicolon chaining (`cat /etc/passwd | grep root`)
- Error responses that match real Ubuntu behavior

**Exit criteria:** An attacker SSH session exercises the full FUSE pipeline. `cat /etc/nginx/nginx.conf` triggers lazy generation. `touch /tmp/test && ls /tmp` shows the file.

### Circuit Breaker (M2.J)

**Why it's Tier 1:** If Ollama goes down, FUSE calls will hang or error unpredictably. A circuit breaker makes degradation invisible to the attacker.

**Scope:**
- Track per-model failure rate and latency percentile
- Auto-degrade to static templates after N consecutive failures
- Time-based backoff recovery with exponential delay
- No FUSE-level errors visible to attacker during degradation

---

## Tier 2: Important (Realism Polish)

These significantly improve the believability of the deception.

### Entropy Engine

**Why it matters:** A filesystem where every file was modified at the same timestamp is instantly suspicious. Entropy simulation makes the filesystem feel alive.

**Scope:**
- Gradual log file growth (`/var/log/syslog`, `/var/log/auth.log`)
- Cache and temp file churn
- Service-realistic patterns (nginx access logs grow during "business hours")

### Aging System

**Why it matters:** Attackers subconsciously trust chronology. A machine where `/etc/passwd` was modified in 2024, `/var/log/nginx/access.log` was modified today, and `~/.bash_history` was modified yesterday feels real.

**Scope:**
- Realistic `mtime`/`atime`/`ctime` distribution across the filesystem
- OS files dated to installation time, config files dated to setup time, logs dated to recent activity
- Gradual timestamp drift rather than static values

### Provenance Metadata

**Why it matters:** Lets a red-team researcher trust or distrust what they're looking at.

**Scope (simplified — only track what you'll actually inspect):**
- `model` — which Ollama model generated this
- `file_class` — credential, config, log, etc.
- `prompt_version` — which prompt template was used
- `generated_at` — timestamp
- `validated` — did the semantic validator pass

~~Removed:~~ `temperature`, `top_p`, `seed`, `prompt hash`, `model hash`, `persona` — forensic noise.

### Predictive Generation

Already partially implemented in `readdir()` prewarm. Extend to predict likely next paths based on traversal patterns.

---

## Tier 3: Later (Infrastructure)

These make sense **after** the deception has been validated with real attacker sessions.

### Storage Lifecycle (Simplified)

The original 4-tier storage system (Hot → Warm → Cold → Archive) is enterprise architecture syndrome for the current scale.

**Simplified to:**
```
Redis (hot) → PostgreSQL (cold) → Delete
```

Blobs aged out on session expiry. Add tiers later only if Redis memory pressure becomes measurable.

### Operational Hardening

Canary deployments, model rollout strategies, blue-green inference — these are important **after people actually use the software**. Optimizing deployment of software nobody has deployed yet is a classic startup mistake.

### SIEM Integrations

Splunk, Sentinel, Elastic connectors. Nobody installs software because it supports Splunk. They install it because it solves a problem. Connectors come after validation.

---

## Tier 4: Only If Needed

These should only be built if concrete evidence (attacker data, user requests) justifies them.

### A/B Testing

~~Removed from M2.G.~~ Attackers aren't filling out satisfaction surveys. Instead, track operational metrics that actually indicate deception quality (see KPIs below).

### Complex Fidelity Experiments

Three fidelity levels (cheap, normal, premium) are enough. Eight tiers is an MMO skill tree. Don't maintain what won't be measured.

### Multi-Instance Scaling

One machine. One Redis. One PostgreSQL. One Ollama. That's enough. Kubernetes syndrome is not a feature.

### Advanced Rollout Strategies

Version promotion, blue-green inference. Build this when the user base demands it.

---

## Attacker-Facing KPIs

This is the biggest gap. Tons of architecture, almost no attacker-facing measurement. These metrics tell you whether the deception is actually working.

| Metric | Why It Matters | Source |
|---|---|---|
| Average session duration | Measures realism — longer = more believable | `session_evidence.duration_seconds` |
| Commands executed per session | Interaction depth | `session_evidence.commands` |
| Unique directories visited | Exploration behavior | `session_evidence.visited_files` |
| Percentage of cache misses | AI workload indicator | Orchestrator metrics |
| AI generation latency (P50, P95) | Performance | Prometheus `chronos_generation_latency_seconds` |
| Honeypot detection attempts | Realism indicator — env checks, kernel probes | CommandAnalyzer |
| Time before first exploit | Attacker confidence | `session_evidence.first_suspicious_command` timestamp |
| Validator rejection rate | Signal of model drift | SemanticValidator |
| MTTD (Mean Time To Detection) | Primary deception quality metric | EvidenceCollector |

---

## Delivery Timeline (Mermaid)

```mermaid
gantt
  title Mirage Program Roadmap (Apate Repo)
  dateFormat YYYY-MM-DD
  axisFormat %b %Y

  section Phase 1 — Core Platform (Completed)
  Foundation and architecture baseline     :done, p1a, 2025-08-24, 90d
  Layer 0 Rust + integration hardening     :done, p1b, 2025-11-21, 70d
  Gateway/Watcher/Skills completion       :done, p1c, 2026-02-01, 20d
  Validation docs + test consolidation      :done, p1d, 2026-02-25, 10d

  section Phase 2 — AI Integration (In Progress)
  AI generation pipeline (M2.A–M2.F)      :done, p2a, 2026-03-03, 120d
  Overseer Dashboard (egui)           :done, p2b, 2026-07-14, 8d
  Tier 1: SSH→FUSE + Circuit Breaker      :active, p2c, 2026-07-22, 30d
  Tier 2: Entropy + Aging + Provenance      :p2d, after p2c, 30d
  Phase 2 close                :milestone, p2e, after p2d, 1d
```

---

## Governance and Change Control

- Any roadmap modification must update this file and reference evidence (commit IDs, test outputs, or docs links)
- Naming must remain consistent:
 - Repo: Apate
 - Product: Mirage
 - Framework: Chronos
- AI features are accepted only if they preserve deterministic truth and improve operator clarity
- New features require a concrete answer to: **"Does this increase attacker dwell time?"**

---

## Next Review Checkpoint

- **Roadmap review cadence:** bi-weekly during Phase 2
- **Immediate next checkpoint:** after SSH→FUSE routing is validated with a live attacker session

*Last Updated: July 2026 — Strategic reprioritization based on external architecture review.*
