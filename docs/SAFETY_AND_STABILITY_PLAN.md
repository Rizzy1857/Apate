# Apate Safety & Stability Plan

**Objective**: Define critical safety nets, fail-checks, and reinforcements for each layer of the Cognitive Deception Framework to ensure operational stability during the upcoming 2-week field test and beyond.

---

## 🛡️ Phase 1: Reflex & Intuition (Critical for Field Test)

### Layer 0: Reflex Layer (Rust) - Weeks 1-6
*Focus: Deterministic Safety & Low Latency*

#### Week 1-2: FFI & Core Logic
- **Safety Net**: **FFI Boundary Protection**
    - [x] Input length validation (prevent DoS via massive strings).
    - [x] `panic::catch_unwind` in Rust extern functions to prevent crashing the Python interpreter.
    - [x] GIL release (`py.allow_threads`) for any computation >1ms.
- **Fail-Check**: **Type Safety Verification**
    - [ ] Strict type checking on all PyO3 conversions.
    - [ ] `Result<T, PyErr>` return types for *all* exposed functions.

#### Week 3-4: Threat Detection Engine
- **Safety Net**: **Regex Denial of Service (ReDoS) Prevention**
    - [x] Use `regex` crate (linear time) instead of backtracking engines.
    - [ ] Hard timeout (e.g., 10ms) on all pattern matching operations.
- **Reinforcement**: **Zero-Copy Parsing**
    - [ ] Use `Cow<str>` to avoid unnecessary allocations during packet inspection.

#### Week 5-6: Integration & Performance
- **Safety Net**: **Latency Circuit Breaker**
    - [x] If Rust processing takes >5ms for 10 consecutive requests, bypass Layer 0 and fallback to static Python logic.
    - [x] **Fail-Open Design**: If Layer 0 crashes, traffic must pass through to the honeypot (logging the failure) rather than dropping connections.
- **Fail-Check**: **Memory Leak Detection**
    - [ ] Run Valgrind/ASan on Rust extension during CI.

---

### Layer 1: Intuition Layer (Predictive Modeling) - Weeks 7-14
*Focus: Stability of Probabilistic Models*

#### Week 7-8: Mathematical Foundation (PST/Markov)
- **Safety Net**: **Zero-Frequency Smoothing (Kneser-Ney)**
    - [ ] **Critical**: Ensure unseen commands never return `Probability = 0.0` (which causes divide-by-zero or logic errors).
    - [ ] **Input Sanitization**: Strip non-printable characters before feeding to PST to prevent state explosion.
- **Fail-Check**: **Model State Bounding**
    - [ ] **Max Depth Limit**: Cap PST depth at 5 to prevent exponential memory growth.
    - [ ] **Node Pruning**: Automatically prune low-probability branches if memory usage >500MB.

#### Week 9-10: Service-Specific Models
- **Safety Net**: **Prediction Confidence Thresholds**
    - [ ] **Low Confidence Fallback**: If prediction confidence < 0.4, do *not* act on it. Log it only.
    - [ ] **Hallucination Guard**: Verify predicted command exists in the allowed "fake filesystem" before suggesting it.

#### Week 11-12: Performance Optimization
- **Reinforcement**: **Inference Timeouts**
    - [ ] Hard timeout of 50ms for any prediction. If timeout, return "No Prediction".
- **Fail-Check**: **Concurrent Access Safety**
    - [ ] Ensure model inference is thread-safe (Rust `Arc<RwLock>`) if accessed by multiple sessions.

#### Week 13-14: Integration & Training
- **Safety Net**: **Model Versioning & Rollback**
    - [ ] Load models with a checksum verification.
    - [ ] Keep `model_v_prev.bin` available. If `model_v_curr.bin` fails to load or errors >1% of requests, auto-rollback.
- **Fail-Check**: **Drift Detection**
    - [ ] Monitor "Unseen Command Ratio". If >20% of commands are new, trigger alert (model is stale).

---

## 🧪 Phase 1 Field Test Readiness (Weeks 15-16)

**Pre-Deployment Checklist**:
1. **Load Shedding**: If CPU > 90%, disable Layer 1 (Intuition) and run only Layer 0 + Core.
2. **Disk Guard**: Stop logging raw payloads if Disk Usage > 85%.
3. **Isolation**: Ensure Docker containers have strict resource limits (`cpus: 1.0`, `mem: 1GB`).
4. **Kill Switch**: A single `.env` flag `DISABLE_AI_LAYERS=true` must instantly revert to static honeypot mode.

---

## 🧠 Phase 2: Reasoning Layer (Weeks 1-12)

### Week 1-3: Feature Engineering
- **Safety Net**: **Feature Normalization Guard**
    - [ ] Handle `NaN` or `Infinity` in feature vectors (e.g., division by zero in time-deltas).
    - [ ] Clip outliers to [p1, p99] range to prevent model instability.

### Week 4-6: Classification Model
- **Fail-Check**: **Cold Start Handling**
    - [ ] Default to "Generic Attacker" profile until N=10 interactions are observed.
- **Reinforcement**: **Ensemble Voting**
    - [ ] Use 3 small Random Forests instead of 1 large one. If they disagree significantly, treat as "Unknown".

### Week 7-9: Strategy Generation
- **Safety Net**: **Action Whitelist**
    - [ ] **Never** allow the model to execute system-level commands on the host.
    - [ ] All generated strategies must map to pre-defined, safe primitives (e.g., `delay_response(ms)`, `show_fake_file()`).

---

## 🎮 Phase 3: Strategy Layer (Weeks 1-14)

### Week 1-4: RL Environment
- **Safety Net**: **Reward Clipping**
    - [ ] Clip rewards to [-1, 1] range to prevent exploding gradients during training.
- **Fail-Check**: **Step Limit**
    - [ ] Enforce max steps per episode (e.g., 100 commands) to prevent infinite loops in simulation.

### Week 5-8: PPO Implementation
- **Reinforcement**: **Safe Exploration**
    - [ ] Use "Safety Layer" that masks out dangerous actions (e.g., "Grant Root") regardless of policy output.

### Week 12-14: Rust Migration
- **Fail-Check**: **Model Divergence Check**
    - [ ] Run Python and Rust models in parallel for 1% of traffic. Alert if outputs differ by >1e-6.

---

## 🎭 Phase 4: Persona Layer (Weeks 1-12)

### Week 1-3: LLM Integration
- **Safety Net**: **PII Redaction**
    - [ ] Regex filter to remove IPs, emails, and keys from prompts *before* sending to LLM API.
- **Fail-Check**: **Cost Circuit Breaker**
    - [ ] Stop calling LLM if daily spend > $5.00.

### Week 4-6: Response Generation
- **Safety Net**: **Prompt Injection Shield (Blue Team LLM)**
    - [ ] **Input**: Scan user command for "Ignore previous instructions".
    - [ ] **Output**: Scan LLM response for "As an AI language model" or revealing system internals.
- **Reinforcement**: **Latency Masking**
    - [ ] Display "typing..." indicator while waiting for LLM to prevent attacker suspicion due to lag.
