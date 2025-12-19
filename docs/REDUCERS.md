# Layer 0 Reducers

Fast, deterministic, and "boring" primitives for the Mirage cognitive deception framework.
# Layer 0 Reducers (Contract + Router)

Fast, deterministic, “boring” primitives for the Mirage cognitive deception framework.

## Philosophy

Layer 0 exists to be **fast and dumb**. It never predicts intent, never adapts creatively, and always fails boringly.
Layer 0 exists to be **fast and dumb**. It never predicts intent, never adapts creatively, and always fails boringly. It answers only three questions:

1. What protocol is this most likely?
2. Is this boring enough to auto-respond?
3. Is this interesting enough to escalate?

In the home profile, Layer 0 never drops traffic. It observes, tags, responds, and escalates.

### Core Constraints

1. **Deterministic & Stateless** (or bounded-state)
   - No clever logic, no intent prediction
   - Reflex responses only

2. **Boring Failures**
   - Protocol misclassification → dead socket, timeout, malformed banner
   - Never: intelligent fallback, verbose error, fast rejection

3. **Verdict-Only Caching**
   - Cache metadata (boring/L1/noise verdicts)
   - **Never** cache responses (prevents determinism fingerprinting)

4. **Downward Degradation**
   - Circuit breaker: L4 → L3 → L2 → L1 → static
   - **Never** upward (static → smart → weird)

5. **Reflex Responses Only**
   - Aho-Corasick/Bloom triggers: fake errors, simulated crashes
   - **Never**: blocks, alerts, adaptive responses

6. **Rate Stats Isolation**
   - Exposed **only** to Layer 0 and Layer 3
   - Not Layer 1 (different signals: automation vs. intent)

## Reducers

### 1. Protocol Classifier (`classify_protocol_fast`)

**Purpose**: Byte-prefix classification without regex for routing efficiency.

**Constraint**: Misclassification must fail boringly.

```rust
let proto = classify_protocol_fast(data);
match proto {
    Protocol::SSH => route_to_ssh_emulator(),
    Protocol::Unknown => boring_failure_response(Protocol::SSH),
    _ => // ...
}
```

**Key**: If SSH is misclassified as HTTP, respond with dead socket or slow timeout, not a clever fallback.

### 2. Aho-Corasick Multi-Match (`NoiseDetector`)

**Purpose**: Fast detection of known garbage (scanners, mass exploit kits).

**Constraint**: Only triggers reflex responses, never influences strategy.

```rust
**Purpose**: Fast detection of obvious junk (tiny immutable core ≤ 20 patterns).
if let Some(pattern_idx) = detector.is_known_noise(payload) {
**Constraint**: Returns a hint tag; never drops; never influences strategy directly.
    return detector.boring_noise_response(pattern_idx);
}
```
if let Some(idx) = detector.check_hint(payload) {
        // Reflex-only: pick a boring response shape
        let _hint = detector.boring_noise_response(idx);
        // Tag EXPLOIT_HINT if needed; routing is handled separately
}

**Purpose**: Cache verdict metadata to reduce load without reducing realism.

**Constraint**: Cache verdicts, **not** responses.

```rust
let cache = VerdictCache::new(1000, 1000);
let key = VerdictCache::cache_key(ip, payload);

if let Some(verdict) = cache.get(key) {
    // Verdict cached, but response MUST still vary
    return generate_varied_response(verdict);
}
```

**Key**: Attackers test determinism by repeating commands. Response timing/formatting must vary even if verdict is cached.

### 4. Sliding Rate Stats (`RateStats`, `RateTracker`)

**Purpose**: Per-IP behavioral shaping to detect automation.

**Constraint**: Exposed **only** to Layer 0 and Layer 3 (not Layer 1).

```rust
**Purpose**: Per-IP behavioral hints (not verdicts) to detect automation.
stats.record();

if stats.is_automated() {
    // Inject latency, micro-errors to degrade bot confidence
    add_latency_jitter();
}
```

**Metrics**:
- Requests per second
- Burstiness score (0.0 = steady, 1.0 = bursty)
**States**:
- `Normal` | `Bursty` | `Insane`
- Derived from RPS and inter-arrival variance (coarse only)
**Purpose**: Drop obvious benign scanner noise early.

**Constraint**: False positive → static path only, **never** drop connection.
**Purpose**: Tag probable benign scanner noise. No drops in Layer 0.
```rust
**Constraint**: Tags as `PROBABLE_NOISE`; Layer 1+ decides deprioritization.

if bloom.is_known_benign(ip, payload) {
    // Route to static emulation (safe on false positive)
let bloom = ScannerNoiseFilter::new(10_000, 0.01, ProfileFlags::HOME);
if bloom.is_probable_noise(ip, payload) {
        // Tag only; do not drop in L0
}
**Key**: Bloom filters have false positives. In Mirage, FP → static emulation is acceptable. FP → connection drop breaks MTTD.

### 6. Adaptive Circuit Breaker (`AdaptiveCircuitBreaker`)

**Purpose**: Dynamic degradation under load while preserving realism.

**Purpose**: Dynamic work shedding under load while preserving security posture.

**Constraint**: Degrade **downward only** (L4→L3→L2→L1→static). Never relax suspicion thresholds; only skip optional analysis in enterprise profile.
let cb = AdaptiveCircuitBreaker::new();
cb.record_latency(latency_ms);

let cb = AdaptiveCircuitBreaker::new(ProfileFlags::ENTERPRISE);
let level = cb.degradation_level();
match level {
    DegradationLevel::Normal => invoke_all_layers(),
    DegradationLevel::L3Only => skip_layer4(),
    DegradationLevel::StaticOnly => skip_all_cognitive_layers(),
    // ...
}
```

**Key**: Circuit breaker **never** makes the system "smarter" under stress—only quieter, flatter, more boring.

## Why This Matters for MTTD

Mirage's goal is 45–60 minute MTTD by delaying attacker realization.

Layer 0 reducers support this by:

1. **Preventing early fingerprinting** (boring failures, no clever logic)
2. **Preserving response consistency** (verdict caching without response caching)
3. **Protecting higher layers from noise** (Aho-Corasick, Bloom filters)
4. **Ensuring cognitive layers add value** (short-circuit on known garbage)
5. **Staying stable under load** (downward degradation, not weird behavior)

Think of Layer 0 as **stage lighting**: it doesn't perform the play, it just makes sure nobody sees the cables.

## Usage

### Rust (Production)

```rust
use rust_protocol::reducers::*;

// Protocol classification
let proto = classify_protocol_fast(data);

// Noise detection
let detector = NoiseDetector::new();
if let Some(idx) = detector.is_known_noise(payload) {
    return detector.boring_noise_response(idx);
}

// Verdict caching
let cache = VerdictCache::new(1000, 1000);
let key = VerdictCache::cache_key(ip, payload);
if let Some(verdict) = cache.get(key) {
    // Use cached verdict, vary response
}

// Rate tracking
let tracker = RateTracker::new(100);
tracker.record(ip);
let stats = tracker.get_stats(ip);
if stats.is_automated() {
    // Shape latency
}

// Bloom filter
let bloom = ScannerNoiseFilter::new(10_000, 0.01);
if bloom.is_known_benign(ip, payload) {
    // Static path
}

// Circuit breaker
let cb = AdaptiveCircuitBreaker::new();
cb.record_latency(latency_ms);
match cb.degradation_level() {
    DegradationLevel::Normal => /* all layers */,
    DegradationLevel::StaticOnly => /* static only */,
    // ...
}
```

### Python (Demo)

let skip_optional = cb.should_skip_optional(); // true when degraded (enterprise)
```bash
cd rust-protocol
python3 demo_reducers.py
```

## Testing

```bash
cd rust-protocol
cargo test reducers --lib
```

## Integration with Mirage Stack

```
Attacker Input
      ↓
[Layer 0: Reducers] ← Fast, dumb, deterministic
      ↓ (short-circuit on known garbage)
[Layer 1: Intuition] ← Smart, predictive
      ↓ (route complex behavior)
[Layer 2: Reasoning] ← Classification
      ↓ (route unknown profiles)
[Layer 3: Strategy] ← RL optimization
      ↓ (route new strategies)
[Layer 4: Persona] ← LLM generation
      ↓
Response
```

**Key Flow**:
- Layer 0 catches ~80% of traffic (known noise, boring probes)
- Layer 1+ handles ~20% (novel/interactive behavior)
- Circuit breaker degrades L4→L3→L2→L1→static under load

## Performance Targets

| Reducer | Target Latency | Notes |
|---------|----------------|-------|
| Protocol classifier | <0.1ms | Byte-prefix only |
| Aho-Corasick | <0.5ms | Precompiled patterns |
| Verdict cache | <0.1ms | HashMap lookup |
| Rate stats | <0.2ms | Atomic operations |
| Bloom filter | <0.1ms | Constant-time checks |
| Circuit breaker | <0.1ms | Atomic state checks |

**Total Layer 0 overhead**: <1ms (well within <5ms budget)

## Anti-Patterns to Avoid

❌ **Clever failures**: `if proto == SSH but looks_like_http { use_smart_fallback() }`  
✅ **Boring failures**: `if proto == Unknown { dead_socket() }`

❌ **Response caching**: `cache.set(key, full_response)`  
✅ **Verdict caching**: `cache.set(key, "NeedsL1")`

❌ **Upward degradation**: `if load_low { enable_layer4() }`  
✅ **Downward degradation**: `if load_high { disable_layer4() }`

❌ **Noise → block**: `if is_noise { drop_connection() }`  
✅ **Noise → fake error**: `if is_noise { fake_timeout() }`

## References

- [AI_Engine_Plan.md](../docs/AI_Engine_Plan.md) - Full Mirage architecture
- [FOUNDATIONS.md](../docs/FOUNDATIONS.md) - Technical foundations
- Aho-Corasick: https://github.com/BurntSushi/aho-corasick
- Bloom filters: https://github.com/jedisct1/rust-bloom-filter

---

**Last Updated**: December 17, 2025  
**Status**: Layer 0 Complete (100%)  
**Next**: Layer 1 Integration (Q1 2026)
