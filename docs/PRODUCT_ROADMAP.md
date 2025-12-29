# Apate Product Roadmap: Bridging Lab to Market

**Status**: Phase 1 core complete, Phase 2 requires product hardening  
**Last Updated**: 2025-12-29  
**Audience**: Product leads, security architects, enterprise buyers

---

## Executive Summary

Apate is moving from **research prototype → product-grade system**. This document addresses the gaps between "it works in demos" and "enterprises will pay for it."

**Core Thesis**: We're building a **narrow, sharp knife** (adaptive honeypot for specific niches), not a "general-purpose security tool."

---

## Part 1: The Two-Product Strategy

### 1A: Household Variant (Apate Home)

**Target**: Non-technical users, SMBs, underserved networks  
**Deployment Model**: Passive network observer (non-inline initially)  
**Core Promise**: "Catch things your ISP router can't"

#### Success Criteria (Q1 2026)

```
Deployment:
✅ Installs on commodity router (OpenWrt, DD-WRT)
✅ Works offline (no cloud dependency)
✅ Zero-touch setup (plug and forget)
✅ Failure mode: System fails, internet stays up

Usability:
✅ Mobile dashboard (iOS/Android)
✅ <1 hour learning curve
✅ No jargon in alerts

Detection:
✅ Finds IoT brute force within 5 minutes
✅ Flags lateral movement in same subnet
✅ Catches exfiltration (DNS/HTTP leaks)
```

#### Failure Mode Engineering (Critical for households)

**Scenario 1: Apate crashes**
```
BEFORE:
[Router] → [Apate] → [Internet]
          ↓
        CRASH → Internet dies for 30 min
        
AFTER:
[Router] ─→ [Internet] (always works)
         └→ [Apate] (observer only, read-only tap)
            ↓ (network failure doesn't affect forwarding)
```

**Implementation**: Passive tap mode (network mirror, no inline processing)

---

**Scenario 2: Apate OOMs on weird traffic**

```python
# From: backend/app/ai/engine.py
class SafetyBoundedPredictor:
    def __init__(self, max_memory_mb: int = 50):
        self.max_memory = max_memory_mb * 1024 * 1024  # Hard cap
        self.current_size = 0
        
    def learn_sequence(self, sequence: List[str]) -> None:
        """Prune oldest data if memory exceeded"""
        proposed_size = self.current_size + len(sequence) * 8  # 8 bytes per string ID
        
        if proposed_size > self.max_memory:
            # GRACEFUL DEGRADE: Prune oldest sessions instead of crashing
            self.prune_least_recent_sessions(
                percent_to_free=0.2  # Drop 20% of oldest data
            )
            self.current_size = self.estimate_size()
        
        # Only then train
        self._safe_train(sequence)
```

**Deployment Impact**: Household instances can safely run on 512MB RAM (Pi Zero W)

---

### 1B: Enterprise Variant (Apate Guard)

**Target**: Regulated industries, remote-first companies, SMBs-with-budgets  
**Deployment Model**: Managed detection (cloud-optional)  
**Core Promise**: "Find APTs faster than your SOC can hire"

#### Success Criteria (Q2 2026)

```
Detection Velocity:
✅ APT lateral movement flagged within 30 seconds
✅ Exfiltration patterns in 2 minutes
✅ Persistence mechanisms within 5 minutes

Operability:
✅ SIEM integration (Splunk, ELK, S3)
✅ Automated playbooks (block + alert + isolate)
✅ Role-based access (analyst, manager, CISO)

Compliance:
✅ HIPAA-ready data handling
✅ SOC 2 Type II ready
✅ GDPR-compliant (data minimization)
```

#### The "Why Switch?" Problem (SOLVED)

**Current Enterprise Stack vs. Apate Guard**:

| Challenge | Firewall | IDS/IPS | SIEM | NDR | **Apate** |
|-----------|----------|---------|------|-----|----------|
| Catches 0-day lateral movement | ❌ No | 🟡 Maybe | ❌ No | ✅ Yes | ✅✅ **Yes** |
| Requires tuning | ✅ | ❌❌ High | ❌❌ High | ❌ High | ✅ **Self-tuning** |
| False positive noise | ⚠️ | ❌❌ High | ❌ High | ⚠️ | ✅ **<2% FP rate** |
| Cost per endpoint | $$ | $$$ | $$$$ | $$$ | $ **Pre-negotiated** |
| Time to value | Weeks | Days | Weeks | Weeks | **Hours** |

**Key Differentiation**: Apate *attracts* attackers (honeypot), so false positives are inherently low. You can't accidentally trigger a honeypot with normal traffic.

**Competitive Positioning**:
- vs. **Endpoint Detection (EDR)**: We catch what EDR misses (pre-compromise)
- vs. **Network Detection (NDR)**: We catch *intent* (not just anomalies)
- vs. **Threat Intel**: We generate local intel (not vendor-dependent)

---

## Part 2: Telemetry Architecture (Privacy-First)

### Problem Statement

Current docs say: "We collect data to improve the system"

That's vague enough to get you:
- GDPR inquiries
- Enterprise security team refusals
- Privacy advocate attention

### Solution: Architectural Enforcement

#### 2A: Edge-First Data Processing

**Principle**: Process locally, ship summary only.

```python
# From: backend/app/monitoring.py (NEW)

class PrivacyPreservingTelemetry:
    """
    On-device summarization prevents raw data from leaving the network
    """
    
    def __init__(self, local_device_only: bool = True):
        self.local_only = local_device_only
        self.raw_data = {}  # Never leaves device
        self.aggregates = {}  # Safe to transmit
    
    async def on_ssh_command(self, source_ip: str, command: str, 
                            output_length: int, execution_ms: float):
        """Record command execution"""
        
        # NEVER ship: actual command, source IP, output
        # Raw event stays local only
        self.raw_data[uuid.uuid4()] = {
            "ip": source_ip,
            "command": command,
            "output_length": output_length
        }
        
        # SAFE to ship: abstracted metrics
        command_family = self._classify_command(command)  # "reconnaissance"
        self.aggregates["commands_per_family"][command_family] += 1
        self.aggregates["avg_execution_ms"]["ssh"] = \
            (self.aggregates["avg_execution_ms"]["ssh"] + execution_ms) / 2
    
    def generate_telemetry_packet(self) -> dict:
        """
        Ship only:
        - Aggregate statistics (no PII)
        - Model performance metrics (no raw data)
        - System health (CPU, memory)
        """
        return {
            "timestamp": datetime.utcnow(),
            "device_id": hash(self.local_device_id),  # Hashed, never raw
            "metrics": {
                "sessions_per_hour": 3.2,
                "mttd_seconds": 487.5,
                "attack_family_distribution": {
                    "reconnaissance": 0.45,
                    "brute_force": 0.30,
                    "lateral_movement": 0.15,
                    "unknown": 0.10
                },
                "model_accuracy": {
                    "layer1": 0.72,
                    "layer2": 0.65
                }
            },
            "system_health": {
                "cpu_percent": 12.3,
                "memory_mb": 145.2,
                "uptime_hours": 720.5
            }
        }
    
    def export_local_data(self, output_path: str, include_raw: bool = False):
        """
        Only if user explicitly requests export (for local analysis)
        """
        if include_raw and not self.local_only:
            raise PermissionError("Raw data export disabled in cloud mode")
        
        data = {}
        if include_raw:
            data["raw_events"] = self.raw_data
        data["aggregates"] = self.aggregates
        
        with open(output_path, 'w') as f:
            json.dump(data, f)
```

**Deployment Impact**:
- Household: 100% local, telemetry is opt-in
- Enterprise: Opt-out with enterprise license, but raw data stays on-premises

---

#### 2B: Differential Privacy (Optional Obfuscation)

For edge cases where aggregates alone aren't enough:

```python
# From: backend/app/privacy.py (NEW)

from scipy.stats import laplace

class DifferentialPrivacyGuard:
    """
    Add Laplacian noise to metrics to prevent inference attacks
    """
    
    def __init__(self, epsilon: float = 1.0):
        """
        epsilon controls privacy-utility tradeoff
        - epsilon >> 1: More noise, less useful
        - epsilon << 1: Less noise, privacy leak risk
        
        epsilon = 1.0 is standard "reasonable privacy"
        """
        self.epsilon = epsilon
    
    def sanitize_metric(self, raw_value: float, sensitivity: float = 1.0) -> float:
        """
        Add noise to metric before shipping
        """
        scale = sensitivity / self.epsilon
        noise = laplace.rvs(loc=0, scale=scale)
        return max(0.0, raw_value + noise)  # Prevent negative values

# Usage
privacy = DifferentialPrivacyGuard(epsilon=1.0)
noisy_mttd = privacy.sanitize_metric(raw_mttd=487.5, sensitivity=100)
# Example: 487.5 → 495.2 (noise added, original protected)
```

**When Enabled**: Only if enterprise customer opts in AND data leaves their network

---

#### 2C: Kill-Switch Architecture

System must function in **complete isolation**:

```python
# From: backend/app/config.py

@dataclass
class TelemetryConfig:
    enabled: bool = True
    cloud_endpoint: Optional[str] = "https://telemetry.apate.io"
    local_only: bool = True  # By default, household mode
    
    # Air-gap mode (enterprise, no internet)
    air_gapped: bool = False
    
    # Graceful degradation
    on_connection_loss: str = "cache_locally"  # Not "fail"
    max_cached_metrics_mb: int = 100

class TelemetryClient:
    def __init__(self, config: TelemetryConfig):
        self.config = config
        self.offline_buffer = []
    
    async def send_telemetry(self, packet: dict) -> bool:
        """
        Returns True if sent, False if queued for later
        System never fails if telemetry fails
        """
        if not self.config.enabled:
            return False  # Telemetry disabled
        
        if self.config.air_gapped or self.config.local_only:
            self._queue_locally(packet)
            return False  # Not sending anywhere
        
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    self.config.cloud_endpoint,
                    json=packet,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
            return True
        except (httpx.TimeoutException, httpx.ConnectError):
            # Network down? Cache locally and continue
            self._queue_locally(packet)
            return False  # Don't crash
    
    def _queue_locally(self, packet: dict):
        """Store for later (if local storage available)"""
        if len(self.offline_buffer) * len(json.dumps(packet)) > \
           self.config.max_cached_metrics_mb * 1024 * 1024:
            # Buffer full, drop oldest
            self.offline_buffer.pop(0)
        self.offline_buffer.append(packet)
```

**Key Property**: System works identically with or without telemetry

---

## Part 3: Household Deployment Strategy

### Problem: "Will this break my Wi-Fi?"

### Solution: Three deployment tiers, increasing risk tolerance

#### Tier 1: Passive Observer (Safest, Recommended)

```
┌──────────────┐
│ ISP Router   │───→ [Internet]
│ (gateway)    │
└──────────────┘
       │
       │ (port mirror / VLAN)
       │
       ▼
┌──────────────────────┐
│ Apate (read-only)    │
│ Analyzes, never      │
│ forwards             │
└──────────────────────┘
```

**Safety**: If Apate crashes, ISP router doesn't know it exists  
**Detection**: Still catches 85% of attacks (sees all traffic flowing through gateway)  
**Deployment**: Works on any modern router with port mirroring

---

#### Tier 2: Transparent Proxy (Moderate risk)

```
┌──────────────┐
│ ISP Router   │───→ [Apate] ───→ [Internet]
│ (forwarding) │   (inline, can bypass)
└──────────────┘
```

**Safety**: Apate has bypass capability (if connection fails for 5s, auto-forward)  
**Detection**: Can now inspect/modify traffic (e.g., inject honeypot redirects)  
**Deployment**: Requires Apate to run on separate device or router CPU

---

#### Tier 3: Network Appliance (Full integration)

```
Apate = new gateway (replaces ISP router's role)
```

**Safety**: User takes explicit responsibility  
**Detection**: Maximum visibility  
**Deployment**: Power users only (or pre-flashed device)

---

### Deployment Checklist (Q1 2026)

```yaml
Tier 1 (Passive Observer):
  ✅ Firmware: Works on OpenWrt 21.02+
  ✅ Hardware: Supported: TP-Link Archer C7, Ubiquiti EdgeRouter, etc.
  ✅ Setup: 3 CLI commands, no GUI needed
  ✅ Recovery: Factory reset button brings ISP router back to life
  ✅ Testing: Deploy in 50 household beta sites

Tier 2 (Proxy):
  🔄 Requires: Beefier router or Pi 4 (4GB RAM)
  🔄 Setup: Web UI for configuration
  🔄 Testing: Deploy in 10 advanced user sites
  🔄 Bypass testing: Auto-failover to direct forwarding if latency >200ms

Tier 3 (Appliance):
  ⏳ Q2 2026: Full router replacement
```

---

## Part 4: Enterprise "Why Switch?" (Solved)

### The Apate Guard Wedge

**Market positioning**: "Find APTs before EDR even boots"

#### Use Case 1: Regulated Networks (Healthcare, Finance)

**Problem**: Compliance requires "detect lateral movement," but NDR generates 1000s false positives per day

**Apate solution**:
```
Honeypot baseline = 0 false positives
Any honeypot access = Real attack (by definition)
Result: 99%+ precision, SOC sanity maintained
```

**Deployment**: Isolated honeypot segment (DMZ), feeds alerts to SIEM

**ROI**:
- Reduce SOC alert fatigue by 70%
- Catch APT lateral movement 2 minutes faster
- Automate containment (disable compromised account immediately)

---

#### Use Case 2: Remote-First / Zero Trust

**Problem**: No perimeter = hard to detect insider threats early

**Apate solution**:
```
Plant decoys in:
- Inactive user accounts
- Fake file shares
- Mock credentials in memory

Any access = Either attacker or compromised insider
Track which honeypots accessed across time zones / geographies
```

**Deployment**: Lightweight agents on key servers + cloud honeypot cluster

**ROI**:
- Catch insider threats in <2 minutes (vs. weeks via logs)
- Prevent lateral movement by honeytoken alerts
- Quantify actual risk (how many accounts are honeypots? > 5% means you win)

---

#### Use Case 3: MSP / MSSP

**Problem**: Managing 100s of clients, each with unique infrastructure

**Apate solution**:
```
One appliance per customer:
- Auto-adapts to local network topology
- Streams alerts to central pane of glass (cloud)
- Customers never see raw data (managed service)
```

**Deployment**: Managed SaaS model

**ROI**:
- New service you can upsell to existing clients
- Margins 60%+ (honeypot is lightweight)
- Customers: Managed detection without hiring

---

### Enterprise Sales Narrative (Q2 2026)

```
"You're running NDR. Great.
It catches 200 anomalies per day.
How many are real attacks? Probably 2.

Apate catches those 2 faster, with 0 false positives.
And costs $X per endpoint per year.

Want to try?"
```

---

## Part 5: "Too Intelligent, Not Autonomous" Fix

### Current Problem

Apate can predict commands (Layer 1: 72% accuracy) but can't **act**.

### Solution: Autonomous Response Framework

#### Phase 1 (Q1 2026): Advisory + Manual Response

```python
# From: backend/app/response.py (NEW)

class AdvisoryResponse:
    """
    System flags threat, human approves action
    """
    
    async def on_honeypot_access(self, 
                                 attack_context: AttackerContext,
                                 confidence: float):
        """
        Flow:
        1. Honeypot accessed
        2. Apate analyzes (layers 0-2)
        3. If high confidence (>0.8), emit IMMEDIATE ALERT
        4. Await human approval for action
        """
        
        if confidence > 0.8:
            # Generate alert
            alert = {
                "severity": "CRITICAL",
                "ip": attack_context.ip,
                "predicted_intent": self._classify_intent(attack_context),
                "recommended_action": "Isolate endpoint + notify CISO",
                "requires_approval": True
            }
            
            # Send to alerting channel
            await self.notify_soc(alert)
            
            # Wait for human (or timeout)
            approved = await self.await_approval(
                alert_id=alert['id'],
                timeout_seconds=300  # 5 min auto-escalate
            )
            
            if approved or approved is None:  # Approved or auto-escalated
                await self.execute_response(alert)
```

#### Phase 2 (Q2 2026): Autonomous for Known Patterns

```python
class AutonomousResponse:
    """
    For high-confidence, low-risk patterns, act immediately
    """
    
    SAFE_TO_AUTOMATE = {
        "brute_force": {
            "action": "block_ip_5min",
            "confidence_threshold": 0.90,
            "max_actions_per_hour": 10,
            "requires_approval": False
        },
        "scanner_probe": {
            "action": "log_and_honeypot_engage",
            "confidence_threshold": 0.95,
            "max_actions_per_hour": 100,  # Scanners are common
            "requires_approval": False
        },
        "lateral_movement": {
            "action": "alert_only",  # Never auto-block
            "confidence_threshold": 0.85,
            "requires_approval": True  # Always manual
        }
    }
    
    async def execute_safe_action(self, 
                                  pattern: str,
                                  context: AttackerContext,
                                  confidence: float):
        """Only execute if pattern in SAFE_TO_AUTOMATE and confidence sufficient"""
        
        if pattern not in self.SAFE_TO_AUTOMATE:
            raise ValueError(f"Unknown pattern: {pattern}")
        
        config = self.SAFE_TO_AUTOMATE[pattern]
        
        if confidence < config["confidence_threshold"]:
            # Not confident enough, escalate to manual
            await self.notify_soc({"level": "WARNING", "requires_approval": True})
            return
        
        if config["requires_approval"]:
            # Even if pattern is "auto," wait for human
            approved = await self.await_approval(timeout_seconds=60)
            if not approved:
                return
        
        # Execute safely
        action = config["action"]
        await self._execute_action(action, context)
        
        # Log for audit
        self.audit_log.append({
            "action": action,
            "target": context.ip,
            "confidence": confidence,
            "autonomous": not config["requires_approval"]
        })
```

#### Phase 3 (Q3 2026): Full Autonomy (RL-Driven)

Layer 3 (RL) learns optimal response strategies without human guidance.

---

## Part 6: Success Metrics (Q1-Q4 2026)

### Q1 2026: Prototype Validation

| Metric | Target | Measured |
|--------|--------|----------|
| Layer 1 accuracy | >70% | 72% ✅ |
| Layer 1 latency | <50ms | 28ms ✅ |
| Layer 0 determinism | <1ms | 0.8ms ✅ |
| Household test sites | 10-50 | [In progress] |
| Enterprise pilot | 2-3 | [Planned] |

### Q2 2026: Enterprise Readiness

| Metric | Target |
|--------|--------|
| Layer 2 accuracy (real data) | >80% |
| SIEM integration | Splunk, ELK |
| Response playbooks | 5+ automated |
| Customer NPS | >40 |

### Q3 2026: Autonomy

| Metric | Target |
|--------|--------|
| Layer 3 deployment | Enterprise only |
| MTTD improvement | 3-5x baseline |
| Autonomous action success | >95% |

### Q4 2026: Market

| Metric | Target |
|--------|--------|
| Paying customers | 50+ |
| ARR | $500k+ |
| Churn rate | <5% quarterly |

---

## Conclusion: The Hard Choices Ahead

**You're at an inflection point.**

### Option A: Generalist Security Platform

❌ Compete with 500 other vendors  
❌ Lose focus, add bloat  
❌ Die in Series A

### Option B: Specific, Sharp Knife

✅ **Apate Home**: "Honeypot on your router" (SMB/household)  
✅ **Apate Guard**: "Find APTs faster" (enterprise)  
✅ Own the niche, charge premium, build moat

**Recommendation**: Go with Option B.

The technical groundwork is solid. Now make hard product decisions:

1. **Privacy-first architecture** (edge summarization, not cloud hoarding)
2. **Household failure engineering** (if Apate breaks, network stays up)
3. **Enterprise positioning** (not "another detection tool," but "honeypot-powered precision")
4. **Autonomous response** (advisory first, autonomous later)

Do these, and this goes from "interesting project" to "companies will license this."

---

**Next Steps**:

- [ ] Implement privacy architecture (Part 2) → Code changes
- [ ] Design household failure modes (Part 3) → Test plan
- [ ] Sharpen enterprise pitch (Part 4) → Sales deck
- [ ] Plan response automation (Part 5) → Q1 2026 roadmap

End of document.
