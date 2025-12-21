# Layer 0 Reducers (Contract + Router)

Fast, deterministic, "boring" primitives for the Mirage cognitive deception framework.

## Philosophy

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

7. **No Drop in Home Profile**
   - Never discard interesting payloads in home profile
   - Bloom filter becomes tagging (hint) in Layer 1+
   - AC full corpus moves to Layer 1+; Layer 0 keeps a tiny immutable core

8. **Three Lanes Only**
   - Auto: known proto + low score → instant fake
   - Curious: odd cadence / unknown proto → delayed inconsistent fake + escalate
   - Suspicious: exploit hint / insane rate → immediate escalate

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

### 2. Aho-Corasick Core Hints (`NoiseDetector`)

**Purpose**: Fast detection of obvious junk (tiny immutable core ≤ 20 patterns).

**Constraint**: Returns a hint tag; never drops; never influences strategy directly.

```rust
let detector = NoiseDetector::new();
if let Some(idx) = detector.check_hint(payload) {
    // Reflex-only: pick a boring response shape
    let _hint = detector.boring_noise_response(idx);
    // Tag EXPLOIT_HINT if needed; routing is handled separately
}
```

**Patterns (examples)**: masscan, nmap, shodan, metasploit, NOP sled, obvious spray creds, path traversal.

### 3. Verdict Cache (`VerdictCache`)

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

### 4. Coarse Rate States (`RateStats`, `RateTracker`)

**Purpose**: Per-IP behavioral hints (not verdicts) to detect automation.

**States**:
- `Normal` | `Bursty` | `Insane`
- Derived from RPS and inter-arrival variance (coarse only)

```rust
let stats = rate_tracker.get_stats(ip);
stats.record();

if stats.is_automated() {
    // Inject latency, micro-errors to degrade bot confidence
    add_latency_jitter();
}
```

### 5. Bloom Filter Tagging (`ScannerNoiseFilter`)

**Purpose**: Tag probable benign scanner noise. No drops in Layer 0.

**Constraint**: Tags as `PROBABLE_NOISE`; Layer 1+ decides deprioritization.

```rust
let bloom = ScannerNoiseFilter::new(10_000, 0.01, ProfileFlags::HOME);
if bloom.is_probable_noise(ip, payload) {
    // Tag only; do not drop in L0
}
```

**Key**: Bloom filters have false positives. In Mirage, FP → static emulation is acceptable. FP → connection drop breaks MTTD.

### 6. Adaptive Circuit Breaker (`AdaptiveCircuitBreaker`) — Work Shedding

**Purpose**: Dynamic work shedding under load while preserving security posture.

**Constraint**: Degrade **downward only** (L4→L3→L2→L1→static). Never relax suspicion thresholds; only skip optional analysis in enterprise profile.

```rust
let cb = AdaptiveCircuitBreaker::new(ProfileFlags::ENTERPRISE);
cb.record_latency(latency_ms);

let level = cb.degradation_level();
match level {
    DegradationLevel::Normal => invoke_all_layers(),
    DegradationLevel::L3Only => skip_layer4(),
    DegradationLevel::StaticOnly => skip_all_cognitive_layers(),
    // ...
}
let skip_optional = cb.should_skip_optional(); // true when degraded (enterprise)
```

**Key**: Circuit breaker **never** makes the system "smarter" under stress—only quieter, flatter, more boring.

## Layer 0 Output Contract

```rust
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ResponseProfile { FastFake, SlowFake, Mirror }

#[derive(Debug, Clone)]
pub struct Layer0Output {
  pub proto_guess: Protocol,
  pub response_profile: ResponseProfile,
  pub tags: u32,            // bitflags
  pub escalate: bool,
  pub suspicion_score: u8,  // additive
}

pub fn route_payload(_proto: Protocol, score: u8, tags: u32) -> ResponseProfile {
  if score >= 50 || (tags & tags::EXPLOIT_HINT) != 0 { return ResponseProfile::Mirror; }
  if score >= 20 || (tags & (tags::PROTO_UNKNOWN | tags::ODD_CADENCE)) != 0 { return ResponseProfile::SlowFake; }
  ResponseProfile::FastFake
}
```

## Why This Matters for MTTD

Mirage's goal is 45–60 minute MTTD by delaying attacker realization.

Layer 0 reducers support this by:

1. Prevent early fingerprinting (boring failures; no clever logic)
2. Preserve response variability (cache verdicts, not responses)
3. Protect higher layers from noise (hints and tags; no premature gates)
4. Ensure cascading short-circuit works (3-lane routing contract)
5. Stay stable under load (work shedding instead of posture changes)

Think of Layer 0 as **stage lighting**: it doesn't perform the play, it just makes sure nobody sees the cables.

## Usage

### Rust (Production) — Updated API

```rust
use rust_protocol::reducers::*;

// Protocol classification
let proto = classify_protocol_fast(data);

// Noise hints (tiny AC core)
let detector = NoiseDetector::new();
if let Some(idx) = detector.check_hint(payload) {
    // Tag EXPLOIT_HINT; choose response later via router
}

// Bloom tagging (no drops in L0)
let bloom = ScannerNoiseFilter::new(10_000, 0.01, ProfileFlags::HOME);
let probable_noise = bloom.is_probable_noise(ip, payload);

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

// Circuit breaker (work shedding)
let cb = AdaptiveCircuitBreaker::new(ProfileFlags::ENTERPRISE);
cb.record_latency(latency_ms);
let skip_optional = cb.should_skip_optional();

// Route via 3 lanes
let profile = route_payload(proto, suspicion_score, tag_bits);
match profile {
  ResponseProfile::FastFake => {/* instant fake */}
  ResponseProfile::SlowFake => {/* delayed inconsistent fake + escalate */}
  ResponseProfile::Mirror => {/* escalate immediately */}
}
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
[Layer 0: Reflex] ← Fast, dumb, deterministic, tag-and-route
      ↓ (short-circuit on boring, escalate on suspicious)
[Layer 1: Intuition] ← HMM command prediction
      ↓ (route complex behavior)
[Layer 2: Reasoning] ← ML behavioral classification
      ↓ (route unknown profiles)
[Layer 3: Strategy] ← RL optimization (has access to rate stats)
      ↓ (route new strategies)
[Layer 4: Persona] ← LLM generation
      ↓
Response
```

**Key Flow**:
- Layer 0 catches ~80% of traffic (known noise, boring probes)
- Layer 1+ handles ~20% (novel/interactive behavior)
- Circuit breaker degrades L4→L3→L2→L1→static under load
- Rate stats shared only with Layer 0 and Layer 3; Layer 1 sees only command sequences

## Performance Targets

| Reducer | Target Latency | Notes |
|---------|----------------|-------|
| Protocol classifier | <0.1ms | Byte-prefix only |
| Aho-Corasick | <0.5ms | Tiny core ≤ 20 patterns |
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
✅ **Noise → tag**: `if is_noise { add_tag(PROBABLE_NOISE) }`

❌ **Rate stats in Layer 1**: `layer1.rate_stats = tracker.get_stats()`  
✅ **Rate stats in Layer 0 & 3**: `layer0.rate_stats = tracker`; `layer3.rate_stats = tracker`

## References

- [AI_Engine_Plan.md](../docs/AI_Engine_Plan.md) - Full Mirage architecture
- [FOUNDATIONS.md](../docs/FOUNDATIONS.md) - Technical foundations
- [LAYER0_SUMMARY.md](../docs/LAYER0_SUMMARY.md) - Quick reference
- Aho-Corasick: https://github.com/BurntSushi/aho-corasick
- Bloom filters: https://github.com/jedisct1/rust-bloom-filter

---

**Last Updated**: December 19, 2025  
**Status**: Layer 0 Complete (100%)  
**Next**: Layer 1 Integration (Q1 2026)
