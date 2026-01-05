# Project Mirage - Adaptive Deception Framework

An intelligent honeypot system built on a staged cognitive architecture with a five-layer research roadmap. Mirage augments the robust Apate foundation with progressive, advisory-only behavioral modeling to improve Mean Time To Discovery (MTTD) through context-enrichment rather than autonomous decision-making.

**Primary Metric**: Mean Time To Discovery (MTTD)  
**Current Baseline**: 2–5 minutes (static honeypot)  
**Projected Research Target**: 45–60+ minutes (pending real-world observation data)  
**All MTTD figures beyond Phase 1 are research projections, not validated metrics.**

## 📖 **Documentation**

For a deep dive into the system architecture and implementation details, please refer to the **[🏗️ Technical Foundations](docs/FOUNDATIONS.md)**.

- **[📚 Usage Guide](docs/usage.md)** - Setup and operation
- **[📊 Progress Tracking](docs/progress.md)** - Development status
- **[🧠 AI Engine Plan](docs/AI_Engine_Plan.md)** - Cognitive roadmap
- **[🔧 API Reference](docs/API.md)** - API documentation

## 🎯 What Makes Mirage Different

### The Advisory Cascade

All layers operate in a cascading advisory model—progressively enriching security context without enforcing hard decisions until explicitly authorized. This humility-first design avoids false positives, autonomous blocking, and unintended network impact.

### Five-Layer Cognitive Architecture (Research Roadmap)

- **Layer 0 – Reflex Layer** ✅ (Operational): Fast, deterministic threat tagging in Rust; no intelligence, pure routing
- **Layer 1 – Intuition Layer** ✅ (Operational, advisory-only): Probabilistic sequence modeling (PST-based) to predict likely attacker actions and emit behavioral continuity signals
- **Layer 2 – Reasoning Layer** (Specification-only; advisory-only when implemented): ML-based behavioral clustering to contextualize attacker profiles and influence threat scoring
- **Layer 3 – Strategy Layer** (Specification-only; not implemented): RL-based long-term engagement optimization via strategy generation  
- **Layer 4 – Persona Layer** (Specification-only; not implemented): Context-aware conversational responses using LLMs

### Operational Principles

- **Predict, Don't Act**: Layers 0–2 enrich context; they never block or modify traffic unilaterally
- **Observable Degradation**: System gracefully reduces capability under load (Layers 2+ drop first)
- **Guardrails Dormant**: Privacy and safety modules exist as specifications, not runtime enforcement
- **Passive-Only Observation Phase**: Jan–Mar 2026 data collection with predict-only gating

## 📊 **Project Status**

**Foundation Complete**: 100% ✅  
**Mirage Architecture**: ~30% (Layers 0–1 operational, Layer 2 spec-only advisory)

### Current Implementation Status

| Layer | Component | Status | Mode | Timeline |
|-------|-----------|--------|------|----------|
| **Foundation** | Apate Core (SSH/HTTP/DB) | ✅ Complete | Operational | — |
| **Layer 0** | Reflex Layer (Rust) | ✅ Complete | Deterministic routing | Q4 2025 |
| **Layer 1** | Intuition Layer (PST) | ✅ Complete | Advisory (passive) | Q1 2026 |
| **Layer 2** | Reasoning Layer (ML) | 📋 Specification | Advisory-only (future) | Q2 2026 |
| **Layer 3** | Strategy Layer (RL) | 📋 Specification | Not implemented | Q3 2026 |
| **Layer 4** | Persona Layer (LLM) | 📋 Specification | Not implemented | Q4 2026 |

### MTTD Progression Targets

| Phase | Layers Active | Target MTTD | Basis | Timeline |
|-------|---------------|-------------|-------|----------|
| **Baseline** | Static Foundation | 2–5 min | Measured | Current |
| **Phase 1** | Layer 0+1 (passive) | Not measured | Observation phase | Q1–Q2 2026 |
| **Phase 2** | Layers 0+1+2 (advisory) | 25–35 min | Research projection | Q2–Q3 2026 |
| **Phase 3** | Layers 0+1+2+3 (advisory) | 35–50 min | Research projection | Q3 2026 |
| **Phase 4** | All five layers (advisory) | 45–60+ min | Research projection | Q4 2026 |

## 🤝 Contributing

Please read **[CONTRIBUTING.md](docs/CONTRIBUTING.md)** for details on our code of conduct, and the process for submitting pull requests.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**⚠️ Disclaimer**: This tool is for research and legitimate cybersecurity purposes only. Users are responsible for compliance with applicable laws and regulations.

> [!NOTE]
> **Observation Phase Active (Jan–Mar 2026)**: Layers 0–1 deployed in passive (predict-only) mode for 30–60 days of clean data collection. Layer 2+ are currently specification-only; runtime implementation begins Q2 2026. Guardrails (privacy, safety) exist as architectural specs, not active enforcement. Full test suite (66 tests) passing. See [Progress](docs/progress.md) for implementation details.
