#!/usr/bin/env python3
"""
Layer 0 Reducers Demo
---------------------
Demonstrates the six Layer 0 latency reducers with constraints enforced:
1. Protocol classifier (boring failures)
2. Aho-Corasick noise detection (reflex only)
3. Verdict caching (metadata only)
4. Rate stats (behavioral shaping)
5. Bloom filter (static path on FP)
6. Adaptive circuit breaker (downward degradation)

Key Philosophy:
- Layer 0 is fast and dumb (deterministic, stateless)
- Failures are boring (dead socket, timeout, not clever)
- Degradation is downward only (L4→L3→L2→L1→static)
"""

import time
import random

# Simulated Layer 0 reducers (Python mock—real implementation in Rust)

class Protocol:
    SSH = "ssh"
    HTTP = "http"
    FTP = "ftp"
    SMTP = "smtp"
    UNKNOWN = "unknown"

def classify_protocol_fast(data: bytes) -> str:
    """Fast protocol classification from byte prefix"""
    if not data:
        return Protocol.UNKNOWN
    
    if data[:4] == b"SSH-":
        return Protocol.SSH
    if data[:3] in (b"GET", b"POS", b"PUT", b"DEL", b"HEA", b"OPT"):
        return Protocol.HTTP
    if data[:4] in (b"USER", b"PASS", b"QUIT", b"RETR"):
        return Protocol.FTP
    if data[:4] in (b"HELO", b"EHLO", b"MAIL"):
        return Protocol.SMTP
    
    return Protocol.UNKNOWN

def boring_failure_response(expected: str) -> bytes:
    """Get boring failure response (no clever logic)"""
    failures = {
        Protocol.SSH: b"",  # dead socket
        Protocol.HTTP: b"HTTP/1.0 400 Bad Request\r\n\r\n",
        Protocol.FTP: b"500 Syntax error, command unrecognized.\r\n",
        Protocol.SMTP: b"500 Syntax error, command unrecognized\r\n",
        Protocol.UNKNOWN: b"",
    }
    return failures.get(expected, b"")

class NoiseDetector:
    """Aho-Corasick simulation for known noise patterns"""
    PATTERNS = [
        "masscan", "nmap", "zgrab", "shodan", "censys",
        "metasploit", "msfconsole", "exploit/", "payload/",
        "admin:admin", "root:root", "test:test"
    ]
    
    def is_known_noise(self, payload: bytes) -> int | None:
        """Returns pattern index if matched, None otherwise"""
        text = payload.decode('utf-8', errors='ignore').lower()
        for i, pattern in enumerate(self.PATTERNS):
            if pattern in text:
                return i
        return None
    
    def boring_noise_response(self, pattern_idx: int) -> str:
        """Boring reflex response (fake error, never block)"""
        if pattern_idx < 5:
            return "Connection timed out\n"
        elif pattern_idx < 9:
            return "Segmentation fault (core dumped)\n"
        else:
            return "Authentication failed\n"

class VerdictCache:
    """Cache for verdict metadata only (NOT responses)"""
    def __init__(self, max_size=1000, ttl_ms=1000):
        self.cache = {}
        self.max_size = max_size
        self.ttl_ms = ttl_ms
    
    def cache_key(self, ip: str, payload: bytes) -> int:
        return hash((ip, payload))
    
    def get(self, key: int) -> str | None:
        now = time.time() * 1000
        if key in self.cache:
            verdict, timestamp = self.cache[key]
            if now - timestamp < self.ttl_ms:
                return verdict
            else:
                del self.cache[key]
        return None
    
    def set(self, key: int, verdict: str):
        now = time.time() * 1000
        if len(self.cache) >= self.max_size:
            # Evict oldest
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (verdict, now)

class RateStats:
    """Per-IP request statistics for behavioral shaping"""
    def __init__(self, window_size=100):
        self.timestamps = []
        self.window_size = window_size
    
    def record(self):
        now = time.time() * 1000
        self.timestamps.append(now)
        if len(self.timestamps) > self.window_size:
            self.timestamps.pop(0)
    
    def requests_per_second(self) -> float:
        now = time.time() * 1000
        cutoff = now - 1000
        count = sum(1 for ts in self.timestamps if ts > cutoff)
        return float(count)
    
    def burstiness_score(self) -> float:
        """0.0 = steady, 1.0 = highly bursty"""
        if len(self.timestamps) < 2:
            return 0.0
        
        sorted_ts = sorted(self.timestamps)
        deltas = [sorted_ts[i] - sorted_ts[i-1] for i in range(1, len(sorted_ts))]
        
        if not deltas:
            return 0.0
        
        mean = sum(deltas) / len(deltas)
        if mean == 0:
            return 0.0
        
        variance = sum((d - mean) ** 2 for d in deltas) / len(deltas)
        std_dev = variance ** 0.5
        cv = std_dev / mean  # coefficient of variation
        
        return min(cv / 2.0, 1.0)
    
    def is_automated(self) -> bool:
        """High rate + low burstiness = bot"""
        return self.requests_per_second() > 5.0 and self.burstiness_score() < 0.3

class ScannerNoiseFilter:
    """Bloom filter simulation for benign scanner noise"""
    def __init__(self):
        self.known_benign = set()  # Simplified bloom (real impl has false positives)
    
    def is_known_benign(self, ip: str, payload: bytes) -> bool:
        key = f"{ip}:{payload.decode('utf-8', errors='ignore')}"
        return key in self.known_benign
    
    def mark_benign(self, ip: str, payload: bytes):
        key = f"{ip}:{payload.decode('utf-8', errors='ignore')}"
        self.known_benign.add(key)

class AdaptiveCircuitBreaker:
    """Circuit breaker with downward-only degradation"""
    def __init__(self):
        self.latency_samples = []
        self.degradation_level = 0  # 0=normal, 1=L3, 2=L2, 3=L1, 4=static
    
    def record_latency(self, latency_ms: float):
        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > 100:
            self.latency_samples.pop(0)
    
    def adaptive_threshold(self) -> float:
        """P95 latency threshold"""
        if not self.latency_samples:
            return 5.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[idx]
    
    def degrade(self):
        """Degrade one level (downward only)"""
        if self.degradation_level < 4:
            self.degradation_level += 1
            print(f"  🔻 Degraded to level {self.degradation_level}")
    
    def try_recover(self):
        """Recover one level (only if stable)"""
        threshold = self.adaptive_threshold()
        if threshold < 3.0 and self.degradation_level > 0:
            self.degradation_level -= 1
            print(f"  🔺 Recovered to level {self.degradation_level}")
    
    def get_level_name(self) -> str:
        levels = ["Normal (All Layers)", "L3 Only", "L2 Only", "L1 Only", "Static Only"]
        return levels[self.degradation_level]

# ============================================================================
# DEMO SCENARIOS
# ============================================================================

def demo_protocol_classification():
    print("\n" + "="*60)
    print("DEMO 1: Protocol Classification (Boring Failures)")
    print("="*60)
    
    test_cases = [
        (b"SSH-2.0-OpenSSH_8.9", "valid SSH"),
        (b"GET / HTTP/1.1", "valid HTTP"),
        (b"USER anonymous", "valid FTP"),
        (b"HELO localhost", "valid SMTP"),
        (b"random garbage", "unknown"),
        (b"HTTP on SSH port", "misclassified"),
    ]
    
    for data, desc in test_cases:
        proto = classify_protocol_fast(data)
        print(f"\n  Input: {data[:20]}... ({desc})")
        print(f"  Classified as: {proto}")
        
        if proto == Protocol.UNKNOWN:
            response = boring_failure_response(Protocol.SSH)
            print(f"  Response: {'<dead socket>' if not response else response[:30]}")

def demo_noise_detection():
    print("\n" + "="*60)
    print("DEMO 2: Noise Detection (Reflex Responses Only)")
    print("="*60)
    
    detector = NoiseDetector()
    test_payloads = [
        b"nmap -sV -O target",
        b"metasploit exploit/multi/handler",
        b"login with admin:admin",
        b"normal user request",
    ]
    
    for payload in test_payloads:
        pattern_idx = detector.is_known_noise(payload)
        print(f"\n  Payload: {payload.decode()}")
        if pattern_idx is not None:
            print(f"  ⚠️  Known noise (pattern #{pattern_idx})")
            print(f"  Response: {detector.boring_noise_response(pattern_idx).strip()}")
            print(f"  Action: Fake error (NEVER block/alert)")
        else:
            print(f"  ✅ Not known noise (route to L1)")

def demo_verdict_caching():
    print("\n" + "="*60)
    print("DEMO 3: Verdict Caching (Metadata Only)")
    print("="*60)
    
    cache = VerdictCache(max_size=100, ttl_ms=500)
    
    # Attacker repeats same command to test determinism
    ip = "192.168.1.100"
    payload = b"id; id; id"
    
    print(f"\n  Attacker IP: {ip}")
    print(f"  Repeated command: {payload.decode()}")
    
    for i in range(3):
        key = cache.cache_key(ip, payload)
        verdict = cache.get(key)
        
        if verdict:
            print(f"\n  Attempt {i+1}: Cache hit → {verdict}")
            print(f"  ⚠️  BUT: Response varies (not cached) to avoid determinism")
            # Each response has slight variations
            print(f"       uid=1000(admin) gid=1000(admin) groups={random.randint(100,999)}")
        else:
            print(f"\n  Attempt {i+1}: Cache miss → compute verdict")
            cache.set(key, "NeedsL1")
            print(f"       Cached: NeedsL1 (metadata only)")
        
        time.sleep(0.1)

def demo_rate_stats():
    print("\n" + "="*60)
    print("DEMO 4: Rate Stats (Behavioral Shaping)")
    print("="*60)
    
    human_stats = RateStats()
    bot_stats = RateStats()
    
    # Simulate human (bursty, inconsistent)
    print("\n  Simulating human attacker...")
    for _ in range(20):
        human_stats.record()
        time.sleep(random.uniform(0.05, 0.3))
    
    print(f"  RPS: {human_stats.requests_per_second():.1f}")
    print(f"  Burstiness: {human_stats.burstiness_score():.2f}")
    print(f"  Automated: {human_stats.is_automated()}")
    
    # Simulate bot (steady, rhythmic)
    print("\n  Simulating bot attacker...")
    for _ in range(20):
        bot_stats.record()
        time.sleep(0.05)  # very consistent
    
    print(f"  RPS: {bot_stats.requests_per_second():.1f}")
    print(f"  Burstiness: {bot_stats.burstiness_score():.2f}")
    print(f"  Automated: {bot_stats.is_automated()} ⚠️")
    print(f"  Action: Inject latency/micro-errors to degrade bot confidence")

def demo_bloom_filter():
    print("\n" + "="*60)
    print("DEMO 5: Bloom Filter (Static Path on FP)")
    print("="*60)
    
    bloom = ScannerNoiseFilter()
    
    # Mark some benign scanner traffic
    bloom.mark_benign("1.2.3.4", b"GET /robots.txt")
    bloom.mark_benign("1.2.3.4", b"GET /favicon.ico")
    
    test_cases = [
        ("1.2.3.4", b"GET /robots.txt", "known benign"),
        ("1.2.3.4", b"GET /admin", "new request"),
        ("5.6.7.8", b"GET /robots.txt", "new IP"),
    ]
    
    for ip, payload, desc in test_cases:
        is_benign = bloom.is_known_benign(ip, payload)
        print(f"\n  {desc}: {ip} → {payload.decode()}")
        if is_benign:
            print(f"  ✅ Known benign (Bloom hit)")
            print(f"  Action: Route to static emulation (NOT drop)")
        else:
            print(f"  ❓ Not in Bloom → route normally")
            print(f"  Note: False positive → static path (safe)")

def demo_adaptive_circuit_breaker():
    print("\n" + "="*60)
    print("DEMO 6: Adaptive Circuit Breaker (Downward Only)")
    print("="*60)
    
    cb = AdaptiveCircuitBreaker()
    
    print("\n  Initial state:")
    print(f"  Level: {cb.get_level_name()}")
    
    # Simulate increasing latency
    print("\n  Simulating latency spike...")
    for i in range(10):
        latency = 2.0 + i * 0.5  # 2ms → 6.5ms
        cb.record_latency(latency)
        if latency > 4.0:
            cb.degrade()
    
    print(f"\n  After spike:")
    print(f"  P95 latency: {cb.adaptive_threshold():.1f}ms")
    print(f"  Level: {cb.get_level_name()}")
    
    # Simulate recovery
    print("\n  Simulating recovery (low latency)...")
    for _ in range(20):
        cb.record_latency(1.5)
    
    cb.try_recover()
    print(f"\n  After recovery:")
    print(f"  P95 latency: {cb.adaptive_threshold():.1f}ms")
    print(f"  Level: {cb.get_level_name()}")
    print(f"\n  Note: Degradation is ALWAYS downward (L4→L3→L2→L1→static)")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║  MIRAGE LAYER 0 REDUCERS DEMO                           ║")
    print("║  Philosophy: Fast, Dumb, Boring                         ║")
    print("╚" + "="*58 + "╝")
    
    demo_protocol_classification()
    demo_noise_detection()
    demo_verdict_caching()
    demo_rate_stats()
    demo_bloom_filter()
    demo_adaptive_circuit_breaker()
    
    print("\n" + "="*60)
    print("KEY TAKEAWAYS")
    print("="*60)
    print("✅ Layer 0 is deterministic and stateless")
    print("✅ Failures are boring (dead socket, timeout)")
    print("✅ Cache verdicts, NOT responses")
    print("✅ Degradation is downward only")
    print("✅ Reflex responses only (no blocks/alerts)")
    print("✅ Rate stats for behavioral shaping (L0 + L3 only)")
    print("\n")
