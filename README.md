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

- **Layer 0 - Reflex Layer**: Sub-millisecond deterministic threat detection in Rust
- **Cognitive Pipeline**: Cascading short-circuit logic to route traffic efficiently
- **Layer 1 - Intuition Layer**: Real-time command prediction using Hidden Markov Models  
- **Layer 2 - Reasoning Layer**: Attacker behavioral classification with Machine Learning
- **Layer 3 - Strategy Layer**: Long-term engagement optimization via Reinforcement Learning
- **Layer 4 - Persona Layer**: Context-aware conversational responses using LLMs

### Adaptive Intelligence

- **Predictive Modeling**: Anticipates attacker actions before they happen
- **Behavioral Learning**: Builds comprehensive attacker profiles over time
- **Strategic Optimization**: Learns optimal deception strategies through self-play
- **Dynamic Personas**: Maintains consistent character across extended interactions

## 📊 **Project Status**

**Foundation Complete**: 87% ✅  
**Mirage Architecture**: 3% (Layer 0 in progress)

### Current Implementation Status

| Layer | Component | Status | Target Timeline |
|-------|-----------|--------|-----------------|
| **Foundation** | Apate Core (SSH/HTTP/DB) | ✅ Complete | - |
| **Layer 0** | Reflex Layer (Rust) | 🔄 In Progress | Q4 2025 |
| **Layer 1** | Intuition Layer (HMM) | ⏳ Planned | Q1 2026 |
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
> **Work in Progress**: The AI components (Layers 1-4) described in this document are currently in the planning and development phase. The current codebase reflects the robust static foundation and the initial implementation of Layer 0 (Reflex Layer). Please check back for updates as we implement the cognitive architecture.
