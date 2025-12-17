// Layer 0 Latency Reducers
// -----------------------
// Fast, deterministic, boring primitives for Mirage cognitive stack.
// Key constraints:
// - No clever logic
// - Deterministic and stateless (or bounded-state)
// - Fail boringly, not intelligently
// - Degrade downward only (never upward)

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use aho_corasick::AhoCorasick;
use bloom::{BloomFilter, ASMS};

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

/// Known garbage patterns (scanners, mass exploit kits, spray-and-pray)
/// CONSTRAINT: Only triggers reflex responses (fake errors, simulated crashes)
/// NEVER: blocks, alerts, adaptive responses
pub struct NoiseDetector {
    ac: AhoCorasick,
}

impl NoiseDetector {
    pub fn new() -> Self {
        let patterns = vec![
            // Mass scanners
            "masscan",
            "nmap",
            "zgrab",
            "shodan",
            "censys",
            // Common exploit kit signatures
            "metasploit",
            "msfconsole",
            "exploit/",
            "payload/",
            // Spray patterns
            "admin:admin",
            "root:root",
            "test:test",
            // Binary junk
            "\x00\x00\x00\x00",
        ];

        Self {
            ac: AhoCorasick::new(patterns).unwrap(),
        }
    }

    /// Check if payload matches known noise patterns
    /// Returns pattern index if matched, None otherwise
    pub fn is_known_noise(&self, payload: &[u8]) -> Option<usize> {
        self.ac.find(payload).map(|m| m.pattern().as_usize())
    }

    /// Get boring response for known noise (never blocks, always fake errors)
    pub fn boring_noise_response(&self, pattern_idx: usize) -> &'static str {
        match pattern_idx {
            0..=4 => "Connection timed out\n", // Scanner patterns
            5..=8 => "Segmentation fault (core dumped)\n", // Exploit patterns
            9..=11 => "Authentication failed\n", // Spray patterns
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
// 4. SLIDING RATE STATS (Per-IP Behavioral Shaping)
// ============================================================================

/// Per-IP request statistics for latency shaping
/// CONSTRAINT: Only exposed to Layer 0 and Layer 3 (NOT Layer 1)
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
// 5. BLOOM FILTER (Scanner Noise Only)
// ============================================================================

/// Bloom filter for known benign scanner noise
/// CONSTRAINT: False positive → static path only, NEVER drop connection
pub struct ScannerNoiseFilter {
    bloom: Arc<Mutex<BloomFilter>>,
}

impl ScannerNoiseFilter {
    pub fn new(expected_elements: usize, false_positive_rate: f64) -> Self {
        let bloom = BloomFilter::with_rate(false_positive_rate as f32, expected_elements as u32);
        Self {
            bloom: Arc::new(Mutex::new(bloom)),
        }
    }

    /// Check if IP+payload combo is known benign noise
    pub fn is_known_benign(&self, ip: &str, payload: &[u8]) -> bool {
        let key = format!("{}:{}", ip, String::from_utf8_lossy(payload));
        let bloom = self.bloom.lock().unwrap();
        bloom.contains(&key)
    }

    /// Mark IP+payload as benign noise
    pub fn mark_benign(&self, ip: &str, payload: &[u8]) {
        let key = format!("{}:{}", ip, String::from_utf8_lossy(payload));
        let mut bloom = self.bloom.lock().unwrap();
        bloom.insert(&key);
    }

    /// Get false positive probability (for monitoring)
    pub fn false_positive_rate(&self) -> f64 {
        // BloomFilter doesn't expose false_positive_rate method
        // Return the configured rate (stored during construction would be ideal,
        // but for now we return a placeholder)
        0.01 // 1% default FPR
    }
}

// ============================================================================
// 6. ADAPTIVE CIRCUIT BREAKER (Downward Degradation Only)
// ============================================================================

/// Enhanced circuit breaker with adaptive thresholds
/// CONSTRAINT: Degrades downward (L4→L3→L2→L1→static), never upward
pub struct AdaptiveCircuitBreaker {
    state: AtomicUsize, // CircuitState
    failure_count: AtomicUsize,
    last_failure_time: AtomicU64,
    // Latency histogram for adaptive thresholds
    latency_buckets: [AtomicUsize; 10], // 0-1ms, 1-2ms, ..., 9-10ms, 10+ms
    degradation_level: AtomicUsize, // 0=normal, 1=L3, 2=L2, 3=L1, 4=static
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
    pub const fn new() -> Self {
        const ATOMIC_ZERO: AtomicUsize = AtomicUsize::new(0);
        Self {
            state: AtomicUsize::new(0),
            failure_count: AtomicUsize::new(0),
            last_failure_time: AtomicU64::new(0),
            latency_buckets: [ATOMIC_ZERO; 10],
            degradation_level: AtomicUsize::new(0),
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

    /// Degrade one level (downward only)
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
    fn test_noise_detector() {
        let detector = NoiseDetector::new();
        assert!(detector.is_known_noise(b"nmap scan").is_some());
        assert!(detector.is_known_noise(b"metasploit payload").is_some());
        assert!(detector.is_known_noise(b"benign request").is_none());
    }

    #[test]
    fn test_verdict_cache() {
        let cache = VerdictCache::new(100, 1000);
        let key = VerdictCache::cache_key("192.168.1.1", b"test");
        
        cache.set(key, Verdict::Boring);
        assert_eq!(cache.get(key), Some(Verdict::Boring));
    }

    #[test]
    fn test_rate_stats() {
        let stats = RateStats::new(100);
        
        // Simulate steady requests
        for _ in 0..10 {
            stats.record();
            std::thread::sleep(std::time::Duration::from_millis(100));
        }
        
        let rps = stats.requests_per_second();
        assert!(rps > 0.0 && rps < 15.0);
    }

    #[test]
    fn test_adaptive_circuit_breaker() {
        let cb = AdaptiveCircuitBreaker::new();
        
        // Record fast latencies
        for _ in 0..100 {
            cb.record_latency(2);
        }
        
        let threshold = cb.adaptive_threshold();
        assert!(threshold <= 3);
    }
}
