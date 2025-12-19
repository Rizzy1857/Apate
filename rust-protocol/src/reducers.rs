// Layer 0 Latency Reducers
// -----------------------
// Layer 0 Philosophy: Observe, Tag, Respond, Escalate. Never judge. Never drop.
// "Home Apate is not a firewall. It is a curious liar that wants to see everything."
//
// Layer 0 answers three questions only:
// 1. What protocol is this most likely?
// 2. Is this boring enough to auto-respond?
// 3. Is this interesting enough to escalate?
//
// Key constraints:
// - No clever logic, no intent prediction
// - Deterministic and stateless (or bounded-state)
// - Fail boringly, not intelligently
// - Degrade downward only (work shedding, never relax suspicion)
// - No dropping in home profile

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use aho_corasick::AhoCorasick;
use bloom::{BloomFilter, ASMS};

// ============================================================================
// LAYER 0 CONTRACT
// ============================================================================

/// Profile flags control behavior without changing architecture
#[derive(Debug, Clone, Copy)]
pub struct ProfileFlags {
    pub drop_enabled: bool,           // home=false, enterprise=true
    pub bloom_drop: bool,             // home=false, enterprise=true
    pub benign_sampling: bool,        // home=false, enterprise=true
    pub latency_adaptive_security: bool, // home=false, enterprise=partial
}

impl ProfileFlags {
    pub const HOME: Self = Self {
        drop_enabled: false,
        bloom_drop: false,
        benign_sampling: false,
        latency_adaptive_security: false,
    };

    pub const ENTERPRISE: Self = Self {
        drop_enabled: true,
        bloom_drop: true,
        benign_sampling: true,
        latency_adaptive_security: true,
    };
}

/// Tag bitflags for metadata propagation
pub mod tags {
    pub const PROBABLE_NOISE: u32 = 1 << 0;
    pub const REPEATED_PROBE: u32 = 1 << 1;
    pub const EXPLOIT_HINT: u32 = 1 << 2;
    pub const BURSTY: u32 = 1 << 3;
    pub const ODD_CADENCE: u32 = 1 << 4;
    pub const PROTO_UNKNOWN: u32 = 1 << 5;
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ResponseProfile {
    FastFake,        // Lane 1: instant fake banner/error
    SlowFake,        // Lane 2: delayed + inconsistent
    Mirror,          // Lane 3: escalate immediately
}

/// Layer 0 Output Contract: tag and route, never drop
#[derive(Debug, Clone)]
pub struct Layer0Output {
    pub proto_guess: Protocol,
    pub response_profile: ResponseProfile,
    pub tags: u32,              // Bitflags from tags::*
    pub escalate: bool,
    pub suspicion_score: u8,    // 0-255 additive score
}

impl Layer0Output {
    pub fn new(proto: Protocol) -> Self {
        Self {
            proto_guess: proto,
            response_profile: ResponseProfile::FastFake,
            tags: 0,
            escalate: false,
            suspicion_score: 0,
        }
    }

    pub fn add_tag(&mut self, tag: u32) {
        self.tags |= tag;
    }

    pub fn add_score(&mut self, points: u8) {
        self.suspicion_score = self.suspicion_score.saturating_add(points);
    }
}

// ============================================================================
// 1. PROTOCOL CLASSIFIER (Fast, Boring Failures)
// ============================================================================

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Protocol {
    SSH,
    HTTP,
    FTP,
    SMTP,
    Unknown,
}

impl Protocol {
    pub fn as_str(&self) -> &'static str {
        match self {
            Protocol::SSH => "ssh",
            Protocol::HTTP => "http",
            Protocol::FTP => "ftp",
            Protocol::SMTP => "smtp",
            Protocol::Unknown => "unknown",
        }
    }
}

/// Classify protocol from first bytes (no regex, pure byte prefix)
/// CONSTRAINT: Misclassification must fail boringly (dead socket, timeout, malformed banner)
pub fn classify_protocol_fast(data: &[u8]) -> Protocol {
    if data.is_empty() {
        return Protocol::Unknown;
    }

    // SSH: starts with "SSH-"
    if data.len() >= 4 && &data[0..4] == b"SSH-" {
        return Protocol::SSH;
    }

    // HTTP: starts with HTTP method
    if data.len() >= 3 {
        let prefix = &data[0..3];
        if prefix == b"GET" || prefix == b"POS" || prefix == b"PUT" || prefix == b"DEL" || prefix == b"HEA" || prefix == b"OPT" {
            return Protocol::HTTP;
        }
    }

    // FTP: starts with "USER " or common FTP commands
    if data.len() >= 4 {
        let prefix = &data[0..4];
        if prefix == b"USER" || prefix == b"PASS" || prefix == b"QUIT" || prefix == b"RETR" {
            return Protocol::FTP;
        }
    }

    // SMTP: starts with "HELO", "EHLO", "MAIL"
    if data.len() >= 4 {
        let prefix = &data[0..4];
        if prefix == b"HELO" || prefix == b"EHLO" || prefix == b"MAIL" {
            return Protocol::SMTP;
        }
    }

    Protocol::Unknown
}

/// Get boring failure response for misclassified protocol
pub fn boring_failure_response(expected: Protocol) -> &'static [u8] {
    match expected {
        Protocol::SSH => b"", // dead socket
        Protocol::HTTP => b"HTTP/1.0 400 Bad Request\r\n\r\n",
        Protocol::FTP => b"500 Syntax error, command unrecognized.\r\n",
        Protocol::SMTP => b"500 Syntax error, command unrecognized\r\n",
        Protocol::Unknown => b"",
    }
}

// ============================================================================
// 2. AHO-CORASICK MULTI-MATCH (Known Noise Only)
// ============================================================================

/// TINY immutable core patterns (≤20) for Layer 0 hints only
/// Full pattern set lives in Layer 1+
/// CONSTRAINT: Returns hint tag, never drops
pub struct NoiseDetector {
    ac: AhoCorasick,
}

impl NoiseDetector {
    pub fn new() -> Self {
        // Layer 0 core: only high-confidence exploit strings
        let patterns = vec![
            // Mass scanners (top 5)
            "masscan",
            "nmap",
            "zgrab",
            "shodan",
            "censys",
            // Exploit kits (top 5)
            "metasploit",
            "msfconsole",
            "exploit/",
            "payload/",
            "\\x90\\x90\\x90", // NOP sled
            // Obvious spray (top 5)
            "admin:admin",
            "root:root",
            "test:test",
            "password:password",
            "123456",
            // Binary garbage (top 5)
            "\x00\x00\x00\x00",
            "\x7f\x45\x4c\x46", // ELF header
            "AAAA", // Buffer overflow pattern
            "%s%s%s%s", // Format string
            "../../../../", // Path traversal
        ];

        Self {
            ac: AhoCorasick::new(patterns).unwrap(),
        }
    }

    /// Check if payload matches core patterns
    /// Returns hint tag, NEVER drops
    pub fn check_hint(&self, payload: &[u8]) -> Option<usize> {
        self.ac.find(payload).map(|m| m.pattern().as_usize())
    }

    /// Get boring response hint (reflex only, never blocks)
    pub fn boring_noise_response(&self, pattern_idx: usize) -> &'static str {
        match pattern_idx {
            0..=4 => "Connection timed out\n", // Scanner patterns
            5..=9 => "Segmentation fault (core dumped)\n", // Exploit patterns
            10..=14 => "Authentication failed\n", // Spray patterns
            _ => "Bad request\n",
        }
    }
}

impl Default for NoiseDetector {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// 3. VERDICT CACHE (Metadata Only, Never Outputs)
// ============================================================================

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Verdict {
    Boring,       // Does not require L1+
    NeedsL1,      // Route to Layer 1
    KnownNoise,   // Scanner/mass exploit
}

/// Cache for verdict metadata only
/// CONSTRAINT: Cache verdicts, not responses (prevents determinism fingerprinting)
pub struct VerdictCache {
    cache: Arc<Mutex<HashMap<u64, (Verdict, u64)>>>, // (key) -> (verdict, timestamp)
    max_size: usize,
    ttl_ms: u64,
}

impl VerdictCache {
    pub fn new(max_size: usize, ttl_ms: u64) -> Self {
        Self {
            cache: Arc::new(Mutex::new(HashMap::new())),
            max_size,
            ttl_ms,
        }
    }

    /// Generate cache key from IP and payload fingerprint
    pub fn cache_key(ip: &str, payload: &[u8]) -> u64 {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        ip.hash(&mut hasher);
        payload.hash(&mut hasher);
        hasher.finish()
    }

    /// Check cached verdict
    pub fn get(&self, key: u64) -> Option<Verdict> {
        let now = current_time_ms();
        let mut cache = self.cache.lock().unwrap();

        if let Some((verdict, timestamp)) = cache.get(&key) {
            if now - timestamp < self.ttl_ms {
                return Some(*verdict);
            } else {
                cache.remove(&key);
            }
        }

        None
    }

    /// Store verdict (evict oldest if at capacity)
    pub fn set(&self, key: u64, verdict: Verdict) {
        let now = current_time_ms();
        let mut cache = self.cache.lock().unwrap();

        // Evict oldest if at capacity
        if cache.len() >= self.max_size {
            if let Some(oldest_key) = cache.iter().min_by_key(|(_, (_, ts))| ts).map(|(k, _)| *k) {
                cache.remove(&oldest_key);
            }
        }

        cache.insert(key, (verdict, now));
    }
}

fn current_time_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_millis() as u64
}

// ============================================================================
// 4. SIMPLIFIED RATE STATS (3 Coarse States)
// ============================================================================

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum RateState {
    Normal,
    Bursty,
    Insane,
}

/// Per-IP request statistics for behavioral hints
/// CONSTRAINT: Only exposed to Layer 0 and Layer 3 (NOT Layer 1)
/// Collapsed from fine-grained to 3 coarse states
pub struct RateStats {
    // Sliding window of timestamps (circular buffer)
    requests: Vec<AtomicU64>,
    write_idx: AtomicUsize,
    window_size: usize,
}

impl RateStats {
    pub fn new(window_size: usize) -> Self {
        let mut requests = Vec::with_capacity(window_size);
        for _ in 0..window_size {
            requests.push(AtomicU64::new(0));
        }

        Self {
            requests,
            write_idx: AtomicUsize::new(0),
            window_size,
        }
    }

    /// Record a request timestamp
    pub fn record(&self) {
        let now = current_time_ms();
        let idx = self.write_idx.fetch_add(1, Ordering::Relaxed) % self.window_size;
        self.requests[idx].store(now, Ordering::Relaxed);
    }

    /// Calculate requests per second (last N requests)
    pub fn requests_per_second(&self) -> f64 {
        let now = current_time_ms();
        let cutoff = now.saturating_sub(1000); // 1 second window

        let count = self.requests.iter()
            .filter(|ts| ts.load(Ordering::Relaxed) > cutoff)
            .count();

        count as f64
    }

    /// Calculate burstiness score (0.0 = steady, 1.0 = highly bursty)
    pub fn burstiness_score(&self) -> f64 {
        let mut timestamps: Vec<u64> = self.requests.iter()
            .map(|ts| ts.load(Ordering::Relaxed))
            .filter(|&ts| ts > 0)
            .collect();

        if timestamps.len() < 2 {
            return 0.0;
        }

        timestamps.sort_unstable();

        // Calculate inter-arrival time variance
        let mut deltas = Vec::new();
        for i in 1..timestamps.len() {
            deltas.push(timestamps[i] - timestamps[i - 1]);
        }

        let mean = deltas.iter().sum::<u64>() as f64 / deltas.len() as f64;
        let variance = deltas.iter()
            .map(|&d| (d as f64 - mean).powi(2))
            .sum::<f64>() / deltas.len() as f64;

        let std_dev = variance.sqrt();
        let cv = if mean > 0.0 { std_dev / mean } else { 0.0 };

        // Normalize to 0-1 range (CV typically < 2)
        (cv / 2.0).min(1.0)
    }

    /// Determine if behavior looks automated (clean, rhythmic)
    pub fn is_automated(&self) -> bool {
        let rps = self.requests_per_second();
        let burstiness = self.burstiness_score();

        // High rate + low burstiness = bot
        rps > 5.0 && burstiness < 0.3
    }

    /// Get coarse rate state (collapsed from fine-grained)
    pub fn rate_state(&self) -> RateState {
        let rps = self.requests_per_second();
        let burstiness = self.burstiness_score();

        if rps > 20.0 || (rps > 10.0 && burstiness > 0.8) {
            RateState::Insane
        } else if rps > 5.0 || burstiness > 0.6 {
            RateState::Bursty
        } else {
            RateState::Normal
        }
    }
}

/// Global per-IP rate tracking
pub struct RateTracker {
    stats: Arc<Mutex<HashMap<String, Arc<RateStats>>>>,
    window_size: usize,
}

impl RateTracker {
    pub fn new(window_size: usize) -> Self {
        Self {
            stats: Arc::new(Mutex::new(HashMap::new())),
            window_size,
        }
    }

    /// Get or create stats for an IP
    pub fn get_stats(&self, ip: &str) -> Arc<RateStats> {
        let mut stats = self.stats.lock().unwrap();
        stats.entry(ip.to_string())
            .or_insert_with(|| Arc::new(RateStats::new(self.window_size)))
            .clone()
    }

    /// Record request for IP
    pub fn record(&self, ip: &str) {
        let stats = self.get_stats(ip);
        stats.record();
    }

    /// Clean up old entries (periodic maintenance)
    pub fn cleanup_inactive(&self, max_age_ms: u64) {
        let now = current_time_ms();
        let mut stats = self.stats.lock().unwrap();
        
        stats.retain(|_, rate_stats| {
            // Keep if any timestamp is recent
            rate_stats.requests.iter().any(|ts| {
                let t = ts.load(Ordering::Relaxed);
                t > 0 && now - t < max_age_ms
            })
        });
    }
}

// ============================================================================
// 5. BLOOM FILTER (Tagging Only - No Drops)
// ============================================================================

/// Bloom filter for noise tagging (moved from gate to hint)
/// CONSTRAINT: Tags as PROBABLE_NOISE, NEVER drops in home profile
/// NOTE: Full bloom logic should migrate to Layer 1+ for advanced tagging
pub struct ScannerNoiseFilter {
    bloom: Arc<Mutex<BloomFilter>>,
    profile: ProfileFlags,
}

impl ScannerNoiseFilter {
    pub fn new(expected_elements: usize, false_positive_rate: f64, profile: ProfileFlags) -> Self {
        let bloom = BloomFilter::with_rate(false_positive_rate as f32, expected_elements as u32);
        Self {
            bloom: Arc::new(Mutex::new(bloom)),
            profile,
        }
    }

    /// Check if IP+payload combo is probable noise (hint, not verdict)
    pub fn is_probable_noise(&self, ip: &str, payload: &[u8]) -> bool {
        let key = format!("{}:{}", ip, String::from_utf8_lossy(payload));
        let bloom = self.bloom.lock().unwrap();
        bloom.contains(&key)
    }

    /// Mark IP+payload as probable noise for future tagging
    pub fn mark_noise(&self, ip: &str, payload: &[u8]) {
        let key = format!("{}:{}", ip, String::from_utf8_lossy(payload));
        let mut bloom = self.bloom.lock().unwrap();
        bloom.insert(&key);
    }

    /// Get false positive probability (for monitoring)
    pub fn false_positive_rate(&self) -> f64 {
        0.01 // 1% default FPR
    }
}

// ============================================================================
// 6. ADAPTIVE CIRCUIT BREAKER (Downward Degradation Only)
// ============================================================================

/// Circuit breaker with work shedding (NEVER relax suspicion)
/// CONSTRAINT: High latency → skip optional analysis, keep thresholds constant
/// Degrades downward (L4→L3→L2→L1→static), never upward
pub struct AdaptiveCircuitBreaker {
    state: AtomicUsize, // CircuitState
    failure_count: AtomicUsize,
    last_failure_time: AtomicU64,
    // Latency histogram for adaptive thresholds
    latency_buckets: [AtomicUsize; 10], // 0-1ms, 1-2ms, ..., 9-10ms, 10+ms
    degradation_level: AtomicUsize, // 0=normal, 1=L3, 2=L2, 3=L1, 4=static
    profile: ProfileFlags,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DegradationLevel {
    Normal = 0,  // All layers operational
    L3Only = 1,  // Skip L4
    L2Only = 2,  // Skip L3-L4
    L1Only = 3,  // Skip L2-L4
    StaticOnly = 4, // Skip all cognitive layers
}

impl From<usize> for DegradationLevel {
    fn from(value: usize) -> Self {
        match value {
            0 => DegradationLevel::Normal,
            1 => DegradationLevel::L3Only,
            2 => DegradationLevel::L2Only,
            3 => DegradationLevel::L1Only,
            _ => DegradationLevel::StaticOnly,
        }
    }
}

impl AdaptiveCircuitBreaker {
    pub fn new(profile: ProfileFlags) -> Self {
        const ATOMIC_ZERO: AtomicUsize = AtomicUsize::new(0);
        Self {
            state: AtomicUsize::new(0),
            failure_count: AtomicUsize::new(0),
            last_failure_time: AtomicU64::new(0),
            latency_buckets: [ATOMIC_ZERO; 10],
            degradation_level: AtomicUsize::new(0),
            profile,
        }
    }

    /// Record latency and update histogram
    pub fn record_latency(&self, latency_ms: u64) {
        let bucket_idx = if latency_ms < 10 {
            latency_ms as usize
        } else {
            9
        };
        self.latency_buckets[bucket_idx].fetch_add(1, Ordering::Relaxed);
    }

    /// Calculate adaptive latency threshold (P95)
    pub fn adaptive_threshold(&self) -> u64 {
        let total: usize = self.latency_buckets.iter()
            .map(|b| b.load(Ordering::Relaxed))
            .sum();

        if total == 0 {
            return 5; // Default 5ms
        }

        let p95_count = (total as f64 * 0.95) as usize;
        let mut cumulative = 0;

        for (idx, bucket) in self.latency_buckets.iter().enumerate() {
            cumulative += bucket.load(Ordering::Relaxed);
            if cumulative >= p95_count {
                return idx as u64;
            }
        }

        10 // Max bucket
    }

    /// Get current degradation level
    pub fn degradation_level(&self) -> DegradationLevel {
        DegradationLevel::from(self.degradation_level.load(Ordering::Acquire))
    }

    /// Degrade one level (work shedding only, never relax suspicion)
    pub fn degrade(&self) {
        let current = self.degradation_level.load(Ordering::Acquire);
        if current < 4 {
            self.degradation_level.store(current + 1, Ordering::Release);
        }
    }

    /// Recover one level (only if stable)
    pub fn try_recover(&self) {
        let threshold = self.adaptive_threshold();
        let current = self.degradation_level.load(Ordering::Acquire);

        // Only recover if latency is consistently low
        if threshold < 3 && current > 0 {
            self.degradation_level.store(current - 1, Ordering::Release);
        }
    }

    /// Check if optional work should be skipped (work shedding)
    pub fn should_skip_optional(&self) -> bool {
        // In home profile, never skip (learning priority)
        if !self.profile.latency_adaptive_security {
            return false;
        }

        // In enterprise, skip extras if degraded
        self.degradation_level.load(Ordering::Acquire) >= 2
    }
}

// ============================================================================
// 7. 3-LANE ROUTER (Hard Cap)
// ============================================================================

/// Route payload through one of three lanes based on suspicion score
pub fn route_payload(
    _proto: Protocol,
    suspicion_score: u8,
    tags: u32,
) -> ResponseProfile {
    // Lane 3: Suspicious (immediate escalate)
    if suspicion_score >= 50 || (tags & tags::EXPLOIT_HINT) != 0 {
        return ResponseProfile::Mirror;
    }

    // Lane 2: Curious (delayed + escalate)
    if suspicion_score >= 20 || (tags & (tags::PROTO_UNKNOWN | tags::ODD_CADENCE)) != 0 {
        return ResponseProfile::SlowFake;
    }

    // Lane 1: Auto-respond (instant fake)
    ResponseProfile::FastFake
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_protocol_classification() {
        assert_eq!(classify_protocol_fast(b"SSH-2.0-OpenSSH_8.9"), Protocol::SSH);
        assert_eq!(classify_protocol_fast(b"GET / HTTP/1.1"), Protocol::HTTP);
        assert_eq!(classify_protocol_fast(b"USER anonymous"), Protocol::FTP);
        assert_eq!(classify_protocol_fast(b"EHLO localhost"), Protocol::SMTP);
        assert_eq!(classify_protocol_fast(b"random data"), Protocol::Unknown);
    }

    #[test]
    fn test_noise_detector_no_drop() {
        let detector = NoiseDetector::new();
        // Check hint returns, never drops
        assert!(detector.check_hint(b"nmap scan").is_some());
        assert!(detector.check_hint(b"metasploit payload").is_some());
        assert!(detector.check_hint(b"benign request").is_none());
    }

    #[test]
    fn test_verdict_cache() {
        let cache = VerdictCache::new(100, 1000);
        let key = VerdictCache::cache_key("192.168.1.1", b"test");
        
        cache.set(key, Verdict::Boring);
        assert_eq!(cache.get(key), Some(Verdict::Boring));
    }

    #[test]
    fn test_rate_stats_coarse_states() {
        let stats = RateStats::new(100);
        
        // Simulate slow steady requests (< 5 RPS)
        for _ in 0..3 {
            stats.record();
            std::thread::sleep(std::time::Duration::from_millis(350));
        }
        
        let state = stats.rate_state();
        // Should be Normal (< 5 RPS)
        assert!(matches!(state, RateState::Normal), "Expected Normal, got {:?}", state);
    }

    #[test]
    fn test_adaptive_circuit_breaker_work_shed() {
        let cb = AdaptiveCircuitBreaker::new(ProfileFlags::HOME);
        
        // Record fast latencies
        for _ in 0..100 {
            cb.record_latency(2);
        }
        
        // Home profile never skips optional work
        assert!(!cb.should_skip_optional());
        
        let threshold = cb.adaptive_threshold();
        assert!(threshold <= 3);
    }

    #[test]
    fn test_3_lane_router() {
        // Lane 1: Auto-respond
        let profile = route_payload(Protocol::SSH, 10, 0);
        assert_eq!(profile, ResponseProfile::FastFake);

        // Lane 2: Curious
        let profile = route_payload(Protocol::Unknown, 25, tags::PROTO_UNKNOWN);
        assert_eq!(profile, ResponseProfile::SlowFake);

        // Lane 3: Suspicious
        let profile = route_payload(Protocol::HTTP, 60, tags::EXPLOIT_HINT);
        assert_eq!(profile, ResponseProfile::Mirror);
    }

    #[test]
    fn test_profile_flags() {
        let home = ProfileFlags::HOME;
        assert!(!home.drop_enabled);
        assert!(!home.bloom_drop);

        let enterprise = ProfileFlags::ENTERPRISE;
        assert!(enterprise.drop_enabled);
        assert!(enterprise.bloom_drop);
    }
}
