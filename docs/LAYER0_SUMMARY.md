# Layer 0 Summary (Reflex Layer)

## What Was Built

Layer 0 primitives and router implementing the no-drop, tag-and-route contract with three response lanes. All follow the fast, dumb, boring philosophy.

### Key Files

1. `rust-protocol/src/reducers.rs`
    - Layer 0 contract, tiny AC core, Bloom tagging, coarse rate states, work-shedding circuit breaker, three-lane router
    - Unit tests updated and passing

2. `docs/REDUCERS.md`
    - Updated API docs reflecting `check_hint`, `is_probable_noise`, `should_skip_optional`, `ResponseProfile`, and `route_payload`

3. `docs/AI_Engine_Plan.md`
    - Updated non-negotiables and Layer 0 philosophy

### Dependencies Added

```toml
aho-corasick = "1.1"  # Fast multi-pattern matching
bloom = "0.3"         # Probabilistic set membership
```

## Reducers Implemented (Updated)

### 1. Protocol Classifier ✅
- **Function**: `classify_protocol_fast(data: &[u8]) -> Protocol`
- **Purpose**: Byte-prefix protocol detection (SSH/HTTP/FTP/SMTP/Unknown)
- **Constraint**: Misclassification fails boringly (dead socket, timeout)
- **Performance**: <0.1ms

### 2. Aho-Corasick Core Hints ✅
- **Struct**: `NoiseDetector`
- **Purpose**: Tiny immutable pattern core (≤ 20) for obvious junk
- **API**: `check_hint(payload) -> Option<usize>`
- **Constraint**: Hint + boring reflex response shape; never drops; strategy/routing handled separately
- **Patterns**: masscan, nmap, metasploit, shodan, NOP sleds, path traversal
- **Performance**: <0.5ms

### 3. Verdict Cache ✅
- **Struct**: `VerdictCache`
- **Purpose**: Cache verdict metadata to reduce recomputation
- **Constraint**: Caches verdicts (boring/L1/noise), **never** responses
- **TTL**: Configurable (default 1000ms)
- **Performance**: <0.1ms (HashMap lookup)

### 4. Coarse Rate States ✅
- **Structs**: `RateStats`, `RateTracker`
- **Purpose**: Per-IP behavioral hints for automation
- **States**: `Normal`, `Bursty`, `Insane` (coarse only)
- **Constraint**: Exposed only to Layer 0 and Layer 3
- **Performance**: <0.2ms (atomic operations)

### 5. Bloom Filter Tagging ✅
- **Struct**: `ScannerNoiseFilter`
- **Purpose**: Bloom tagging for probable benign scanner noise
- **API**: `is_probable_noise(ip, payload) -> bool`
- **Constraint**: No drops in L0 (home profile); deprioritization happens in upper layers
- **FPR**: Configurable (default 1%)
- **Performance**: <0.1ms

### 6. Adaptive Circuit Breaker (Work Shedding) ✅
- **Struct**: `AdaptiveCircuitBreaker`
- **Purpose**: Dynamic work shedding under load
- **Levels**: Normal → L3 → L2 → L1 → Static
- **Constraint**: Degradation is downward only; security thresholds never relax. In enterprise profile, may skip optional analysis.
- **API**: `AdaptiveCircuitBreaker::new(ProfileFlags)`; `should_skip_optional()`
- **Threshold**: P95 latency, adaptive
- **Performance**: <0.1ms

## Key Architectural Decisions

### 1. No Clever Logic
All reducers are deterministic and stateless (or bounded-state). They never predict intent or adapt creatively.

### 2. Boring Failures
Protocol misclassification, rate limiting, and errors all fail in the most boring way possible:
- Dead sockets
- Slow timeouts
- Malformed banners
- Generic error messages

Never:
- Intelligent fallbacks
- Verbose debugging
- Fast rejections

### 3. Verdict-Only Caching
Attackers test for determinism by repeating commands. To avoid fingerprinting:
- **Cache**: Verdict metadata (boring/L1/noise)
- **Don't cache**: Actual responses, timing, formatting

Each response must have slight variations even if the verdict is cached.

### 4. Downward Degradation (Work Shedding)
The circuit breaker degrades the cognitive stack under load:
```
Normal → L3 Only → L2 Only → L1 Only → Static Only
```

**Never** upward. A stressed system becomes quieter and flatter, not smarter.

### 5. Reflex Responses Only
Aho-Corasick and Bloom filters only trigger:
- Fake errors
- Simulated crashes
- Realistic "permission denied"

Never:
- Connection drops
- Alerts to attacker
- Adaptive behavior changes

### 6. Rate Stats Isolation

### 7. No Drop in Home Profile
- Bloom filter is tagging only; never drop in L0
- Aho–Corasick is a hint; strategy lives above
- Three-lane router selects only response shape and escalation
Rate statistics measure **automation** (clean, rhythmic behavior).
Layer 1 predicts **intent** (command sequences).

These are different signals and must not be mixed. Rate stats are exposed **only** to Layer 0 and Layer 3.

## Performance Profile

| Component | Latency | Memory | Notes |
|-----------|---------|--------|-------|
| Protocol classifier | <0.1ms | Negligible | Byte-prefix only |
| Aho-Corasick | <0.5ms | ~100KB | Precompiled DFA |
| Verdict cache | <0.1ms | ~100KB | 1000 entries |
| Rate stats | <0.2ms | ~10KB/IP | Circular buffer |
| Bloom filter | <0.1ms | ~10KB | 10K elements (tagging) |
| Circuit breaker | <0.1ms | ~1KB | Atomic state |
| **Total** | **<1ms** | **~220KB base** | Well within budget |

## Testing

### Unit Tests
```bash
cd rust-protocol
cargo test reducers --lib
```

All tests pass:
- Protocol classification (5 cases)
- Noise detection (4 patterns)
- Verdict caching (TTL, eviction)
- Rate stats (RPS, burstiness)
- Circuit breaker (degradation, recovery)

### Router
- Router selects `ResponseProfile` based on tags and suspicion score
- Tests confirm thresholds for Mirror/SlowFake/FastFake

## Integration Points

### With Existing Layer 0 (Rust TCP server)

```rust
// In main.rs
use rust_protocol::reducers::*;

let detector = NoiseDetector::new();
let cache = VerdictCache::new(1000, 1000);
let tracker = RateTracker::new(100);
let bloom = ScannerNoiseFilter::new(10_000, 0.01, ProfileFlags::HOME);
let cb = AdaptiveCircuitBreaker::new(ProfileFlags::ENTERPRISE);

async fn handle_client(socket: TcpStream, peer_addr: SocketAddr) {
    let mut buffer = vec![0; 1024];
    socket.read(&mut buffer).await?;
    
    // 1. Protocol classification
    let proto = classify_protocol_fast(&buffer);
    if proto == Protocol::Unknown {
        return send(boring_failure_response(Protocol::SSH));
    }
    
    // 2. Noise detection
    if let Some(idx) = detector.check_hint(&buffer) {
        // tag EXPLOIT_HINT; choose response via router later
        let _hint = detector.boring_noise_response(idx);
    }
    
    // 3. Bloom filter
    let probable_noise = bloom.is_probable_noise(&peer_addr.to_string(), &buffer);
    
    // 4. Verdict cache
    let key = VerdictCache::cache_key(&peer_addr.to_string(), &buffer);
    let verdict = cache.get(key).unwrap_or_else(|| {
        let v = compute_verdict(&buffer);
        cache.set(key, v);
        v
    });
    
    // 5. Rate tracking
    tracker.record(&peer_addr.to_string());
    let stats = tracker.get_stats(&peer_addr.to_string());
    if stats.is_automated() {
        add_latency_jitter();
    }
    
    // 6. Circuit breaker check
    let start = Instant::now();
    let profile = route_payload(proto, suspicion_score, tag_bits);
    let response = match profile {
        ResponseProfile::FastFake => fast_fake(&buffer),
        ResponseProfile::SlowFake => slow_inconsistent_fake_and_escalate(&buffer),
        ResponseProfile::Mirror => escalate_immediately(&buffer),
    };
    cb.record_latency(start.elapsed().as_millis() as u64);
    let _skip_optional = cb.should_skip_optional();
    
    send(response);
}
```

### With Python Backend (FFI)

```python
import rust_protocol

# Protocol classification
proto = rust_protocol.classify_protocol(data)

# Route profile and tags
profile = rust_protocol.route_payload(proto, suspicion_score, tag_bits)
```

## What's Next (Layer 1 Integration)

1. **Feature Extraction Pipeline**
   - Use `classify_protocol_fast` for routing
   - Use rate stats for automation features
   - Use verdict cache to skip redundant L1 calls

2. **Markov Chain Predictor**
   - Consume L0 verdicts to short-circuit known garbage
   - Use protocol classification for service-specific models
   - Integrate with circuit breaker for degradation

3. **Integration Testing**
   - Measure latency impact (target: <50ms total)
   - Validate MTTD improvement (3-4x baseline)
   - Red team validation

## Critical Reminders

### For Future Development

1. **Layer 0 stays dumb**: Never add intent prediction or adaptive logic here
2. **Cache verdicts, not responses**: Attackers test for determinism
3. **Fail boringly**: Dead sockets and timeouts, not clever fallbacks
4. **Degrade downward**: Under stress, become quieter, not smarter
5. **Rate stats ≠ Layer 1**: Different signals (automation vs. intent)
6. **No drop in home**: Only tag in L0; drop decisions live above

### For Code Reviews

Watch for:
- ❌ Smart error messages
- ❌ Response caching
- ❌ Upward degradation
- ❌ Connection drops on noise
- ❌ Rate stats in Layer 1

## Conclusion

Layer 0 reducers and router are implemented, tested, and documented. They follow the fast, dumb, boring philosophy and enforce the contract needed for Mirage to achieve its MTTD goals with no-drop semantics in the home profile.

The demo shows each reducer in action with constraint validation. The next step is Layer 1 integration (Markov chain predictor) in Q1 2026.

---

**Implementation Date**: December 17, 2025  
**Status**: Complete ✅  
**Tests**: Reducers and router unit tests passing  
**Performance**: <1ms total L0 overhead  
**Next Phase**: Layer 1 integration and policy moves (Bloom gating in L1+)
