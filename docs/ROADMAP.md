# Project Mirage Roadmap

## 🗺️ Strategic Overview

Project Mirage aims to transform the Apate honeypot into a sophisticated **Cognitive Deception Framework**. This roadmap outlines the architectural evolution, key milestones, and security mechanisms designed to achieve a 9-12x improvement in Mean Time To Discovery (MTTD).

---

## 🏗️ 1. Project Architecture

The following diagram illustrates the high-level architecture of the complete system, integrating the Rust Reflex Layer, Python Core, and the Cognitive Engine.

```mermaid
graph TD
    User[Attacker] -->|TCP/IP| LB[Load Balancer]
    LB -->|SSH/HTTP| Rust[Layer 0: Rust Reflex]
    
    Rust -->|Safe Traffic| Pipeline{Cognitive Pipeline}
    
    subgraph "Core Honeypot"
        Pipeline -->|Short Circuit| PyCore[Python Core]
        PyCore -->|SSH| SSH_Emu[SSH Emulator]
        PyCore -->|HTTP| HTTP_Emu[HTTP Emulator]
        PyCore -->|Data| DB[(PostgreSQL)]
        PyCore -->|Cache| Redis[(Redis)]
    end
    
    subgraph "Cognitive Engine"
        Pipeline -->|Novel Threat| L1[Layer 1: Intuition]
        L1 -->|Complex| L2[Layer 2: Reasoning]
        L2 -->|Strategic| L3[Layer 3: Strategy]
        L3 -->|Generative| L4[Layer 4: Persona]
        L4 -.->|Directives| PyCore
    end
    
    subgraph "Monitoring"
        Prometheus --> Grafana
        ELK[ELK Stack]
    end
```

---

## 🧠 2. AI Cognitive Engine

The core of Mirage is the 5-Layer Cognitive Architecture. This diagram details the flow of data and decision-making through the AI layers.

### Cognitive Deception Layers (Cascading Short-Circuit)

To minimize latency, the system uses a **Cascading Short-Circuit** architecture. At each layer, the system evaluates if it has enough information to respond. If yes, it "exits" to the static emulator immediately. Only novel or complex interactions proceed to higher layers.

```mermaid
graph TD
    subgraph "Layer 4: Persona (Generative)"
        L4[LLM Response Generation]
    end
    
    subgraph "Layer 3: Strategy (RL)"
        L3[Reinforcement Learning Agent]
    end
    
    subgraph "Layer 2: Reasoning (ML)"
        L2[Behavioral Classifier]
    end
    
    subgraph "Layer 1: Intuition (Probabilistic)"
        L1[Markov Chain Predictor]
    end
    
    subgraph "Layer 0: Reflex (Deterministic)"
        L0[Rust Threat Engine]
    end

    Input[Attacker Input] --> L0
    
    L0 -->|Known Exploit| Block[Block/Fake Response]
    L0 -->|Safe| L1
    
    L1 -->|Predicted Sequence| Static[Static Emulation]
    L1 -->|Novel Sequence| L2
    
    L2 -->|Known Profile| Static
    L2 -->|Unknown Profile| L3
    
    L3 -->|Standard Strategy| Static
    L3 -->|New Strategy| L4
    
    L4 -->|Generative Response| Output[Response]
    Static -->|Standard Response| Output
    Block -->|Fake Error| Output
```

---

## 🛡️ 3. Security & Fail-Safe Mechanisms

To ensure stability and low latency, Layer 0 implements a **Latency Circuit Breaker**. This state machine ensures the system fails open under load.

```mermaid
stateDiagram-v2
    [*] --> Closed
    
    state "Closed (Normal)" as Closed {
        [*] --> CheckLatency
        CheckLatency --> RunRegex: < 5ms
        RunRegex --> ReturnResult
        CheckLatency --> RecordFailure: > 5ms
        RecordFailure --> CheckThreshold
        CheckThreshold --> [*]: < 10 Failures
    }

    state "Open (Tripped)" as Open {
        [*] --> BypassAI
        BypassAI --> StaticFallback
        StaticFallback --> CheckTimeout
        CheckTimeout --> [*]: < 30s
    }

    state "Half-Open (Recovery)" as HalfOpen {
        [*] --> TestRequest
        TestRequest --> Success: < 5ms
        TestRequest --> Failure: > 5ms
    }

    Closed --> Open: > 10 Failures
    Open --> HalfOpen: After 30s
    HalfOpen --> Closed: Success
    HalfOpen --> Open: Failure
    
    note right of Open
        Fail-Open Design:
        Traffic is never blocked,
        just downgraded to static.
    end note
```

---

## 📅 Execution Timeline

### **Phase 1: Foundation & Reflex (Q4 2025)**
*   **Goal**: Establish Rust infrastructure and sub-millisecond threat detection.
*   **Status**: ✅ **Complete**
*   **Key Deliverables**:
    *   Rust Protocol Library
    *   Threat Detection Engine (Regex)
    *   Latency Circuit Breaker
    *   FFI Safety Wrappers

### **Phase 2: Intuition & Reasoning (Q1-Q2 2026)**
*   **Goal**: Implement predictive modeling and attacker classification.
*   **Status**: 🔄 **In Progress**
*   **Key Deliverables**:
    *   Hidden Markov Models (Layer 1)
    *   Probabilistic Suffix Trees
    *   Random Forest Classifier (Layer 2)
    *   Feature Engineering Pipeline

### **Phase 3: Strategy & Persona (Q3-Q4 2026)**
*   **Goal**: Achieve autonomous strategy optimization and realistic persona generation.
*   **Status**: ⏳ **Planned**
*   **Key Deliverables**:
    *   PPO Reinforcement Learning Agent (Layer 3)
    *   LLM Integration (Layer 4)
    *   Context-Aware Response Generation
    *   Multi-Agent Orchestration

## 🎯 Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| **Mean Time To Discovery (MTTD)** | 2-5 min | **45-60+ min** |
| **System Latency (P99)** | < 1ms | **< 200ms** |
| **Attacker Engagement** | Low | **High** |
