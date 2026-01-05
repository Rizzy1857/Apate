# Project Mirage - Adaptive Cognitive Deception Framework

A next-generation honeypot system that uses a five-layer cognitive architecture to create adaptive, intelligent deception environments. Mirage transforms traditional honeypots from static decoys into dynamic, learning systems that adapt to attacker behavior in real-time.

**Primary Metric**: Mean Time To Discovery (MTTD)  
**Current Baseline**: 2-5 minutes (static honeypot)  
**Target Goal**: 45-60+ minutes (9-12x improvement)

## 📖 **Documentation**

For a deep dive into the system architecture and implementation details, please refer to the **[🏗️ Technical Foundations](docs/FOUNDATIONS.md)**.

- **[📚 Usage Guide](docs/usage.md)** - Setup and operation
- **[📊 Progress Tracking](docs/progress.md)** - Development status
- **[🧠 AI Engine Plan](docs/AI_Engine_Plan.md)** - Cognitive roadmap
- **[🔧 API Reference](docs/API.md)** - API documentation

## 🎯 What Makes Mirage Different

### Five-Layer Cognitive Architecture

- **Layer 0 - Reflex Layer**: Fast, dumb, deterministic tag-and-route in Rust (no-drop, three lanes)
- **Cognitive Pipeline**: Cascading short-circuit logic to route traffic efficiently
- **Layer 1 - Intuition Layer**: Real-time command prediction + Bloom tagging using Hidden Markov Models  
- **Layer 2 - Reasoning Layer**: Attacker behavioral classification with Machine Learning
- **Layer 3 - Strategy Layer**: Long-term engagement optimization via RL (has access to rate stats from L0)
- **Layer 4 - Persona Layer**: Context-aware conversational responses using LLMs

### Adaptive Intelligence

- **Predictive Modeling**: Anticipates attacker actions before they happen
- **Behavioral Learning**: Builds comprehensive attacker profiles over time
- **Strategic Optimization**: Learns optimal deception strategies through self-play
- **Dynamic Personas**: Maintains consistent character across extended interactions

## 📊 **Project Status**

**Foundation Complete**: 100% ✅  
**Mirage Architecture**: 15% (Layers 0–1 passive + infrastructure)

### Current Implementation Status

| Layer | Component | Status | Target Timeline |
|-------|-----------|--------|------------------|
| **Foundation** | Apate Core (SSH/HTTP/DB) | ✅ Complete | - |
| **Layer 0** | Reflex Layer (Rust) | ✅ Complete | Q4 2025 |
| **Layer 1** | Intuition Layer (HMM) | ✅ Complete (Passive) | Q1 2026 |
| **Layer 2** | Reasoning Layer (ML) | ⏳ Planned | Q2 2026 |
| **Layer 3** | Strategy Layer (RL) | ⏳ Planned | Q3 2026 |
| **Layer 4** | Persona Layer (LLM) | ⏳ Planned | Q4 2026 |

### MTTD Progression Targets

| Phase | Layers Active | Target MTTD | Improvement | Timeline |
|-------|---------------|-------------|-------------|----------|
| **Baseline** | Static Foundation | 2-5 min | 1x | Current |
| **Phase 1** | Layer 0+1 | 15-20 min | 3-4x | Q1 2026 |
| **Phase 2** | Layer 0+1+2 | 25-35 min | 5-7x | Q2 2026 |
| **Phase 3** | Layer 0+1+2+3 | 35-50 min | 7-10x | Q3 2026 |
| **Phase 4** | All Five Layers | 45-60+ min | 9-12x | Q4 2026 |

## 🤝 Contributing

Please read **[CONTRIBUTING.md](docs/CONTRIBUTING.md)** for details on our code of conduct, and the process for submitting pull requests.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**⚠️ Disclaimer**: This tool is for research and legitimate cybersecurity purposes only. Users are responsible for compliance with applicable laws and regulations.

> [!NOTE]
> **Observation Phase Active (Jan 2026)**: Layers 0–1 are deployed in passive (predict-only) mode for 30–60 days of clean data collection. All components are functional; Layer 2+ are deferred to Q2+ 2026. Full test suite (66 tests) passing. See [Progress](docs/progress.md) for timeline.
