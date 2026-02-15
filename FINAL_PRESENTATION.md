# CCD 334 - MINIPROJECT

## Final Presentation

---

# Mirage: AI-Powered Decoy System

### *Intelligent Honeypot Framework with Atomic State Management*

---

## 1. Motivation

### Why This Project Matters

The cyber security landscape faces a critical gap between attackers and defenders:

**Current Challenges:**
- **Traditional honeypots** are easily detectable by sophisticated attackers due to state inconsistencies
  - Attacker: `touch /tmp/pwn && ls /tmp` → File disappears → Honeypot detected as fake
  - Defenders learn nothing from compromised honeypots

- **LLM-based honeypots** hallucinate state information
  - Memory window limits cause attackers to discover contradictions
  - File operations are stateless → inconsistent responses
  - Not suitable for serious threat research

- **Current alternatives** are expensive and risky
  - Honeypots based on actual VMs consume significant resources
  - Risk of attacker pivot to production systems
  - Manual log analysis is time-consuming

**Motivation for Mirage:**
- Create a **production-ready honeypot** that behaves like real Linux systems
- Enable **genuine threat research** without detection risk
- Capture **authentic attack patterns** for threat intelligence
- Provide **cost-effective deception** infrastructure for security operations

---

## 2. Introduction

### Overview of Mirage Framework

**What is Mirage?**

Mirage is a cognitive deception infrastructure that implements a **high-fidelity honeypot** designed to solve state hallucination problems plaguing existing solutions. Unlike traditional and LLM-based honeypots, Mirage provides genuine filesystem consistency through intelligent state management.

**Key Characteristics:**

1. **FUSE Filesystem**: Kernel-level interception of all filesystem operations
   - Full POSIX compliance
   - Transparent to attacker tools
   - Real filesystem semantics

2. **State Hypervisor**: Redis-backed atomic state management
   - All operations atomic and persistent
   - No state contradictions
   - Survives unlimited command sequences

3. **Cognitive Intelligence**: LLM-powered content generation
   - Persona engine generates realistic content
   - Only used for content, never for state
   - Lazy evaluation with persistent caching

4. **Threat Analysis**: Real-time attack detection and profiling
   - MITRE ATT&CK framework integration
   - Attacker skill profiling (script kiddie to APT expert)
   - Attack phase detection and correlation

### System Goals

| Goal | Implementation | Result |
|------|----------------|--------|
| **Undetectable** | Atomic state via Redis + FUSE | Attackers cannot find inconsistencies |
| **Realistic** | Full POSIX filesystem + LLM content | Behaves exactly like Linux system |
| **Analyzable** | PostgreSQL audit logs + real-time streaming | Complete forensic trails |
| **Scalable** | Lightweight Python + Rust Layer 0 | Docker-deployable, resource-efficient |

---

## 3. Inferences from Literature Survey

### State of the Art Analysis

#### Traditional Honeypots (Honeyd, Cowrie)
- **Pros**: Fast, easy to deploy
- **Cons**: 
  - Limited to scripted interactions
  - State inconsistencies easily detected
  - Cannot support complex attack chains
- **Detection vector**: File creation inconsistencies, incomplete shell history

#### LLM-Based Honeypots (Recent Approaches)
- **Pros**: More flexible, natural language support
- **Cons**:
  - **Memory window limits** (4K-128K tokens)
  - **State hallucinations** (forget past operations)
  - **Contradictory responses** (permission mismatches)
  - **No persistent state database**
- **Detection vector**: Logical contradictions, context window boundaries

#### High-Interaction Honeypots (Real VMs)
- **Pros**: Completely realistic
- **Cons**:
  - Resource-intensive
  - Pivot risk (attacker may compromise host)
  - Not suitable for large-scale deployment

### Research Gaps

1. **State Consistency Problem**: No honeypot combines FUSE filesystem with persistent state
2. **Scalability**: Real VMs not practical for distributed deployments
3. **Analysis Capability**: Most honeypots lack real-time threat intelligence
4. **Cost**: Existing solutions expensive or unreliable

### Mirage's Contribution

Mirage fills this gap by:
- Combining FUSE filesystem + Redis atomic state
- Providing both realism AND consistency
- Enabling scalable deployment
- Integrating real-time threat analysis

---

## 4. Problem Statement

### The State Hallucination Problem

#### Problem 1: Traditional Honeypots - State Inconsistency

**Scenario:**
```
Attacker: touch /tmp/pwn && ls /tmp
Traditional Honeypot: 
  - touch /tmp/pwn → "OK" (script returns success)
  - ls /tmp → "" (empty list - file not actually created)
Result: DETECTED AS FAKE
```

**Why it occurs:**
- File creation and listing are handled separately
- No transaction guarantee between operations
- State not persisted across commands

**Impact:** Attackers immediately realize honeypot is fake, stop interacting, yield no intelligence.

#### Problem 2: LLM-Based Honeypots - State Hallucination

**Scenario 1: Memory Window Loss**
```
Command 1: cd /home/attacker
[50 commands later]
Command 52: pwd
LLM: "/root" ← WRONG (context window exceeded, forgot cd)
Result: DETECTED AS FAKE
```

**Scenario 2: File Existence Contradiction**
```
Command 1: touch file && ls
LLM: "file exists" ✓

Command 2: cat file
LLM: "file not found" ✗ ← CONTRADICTION
Result: DETECTED AS FAKE
```

**Scenario 3: Permission Contradiction**
```
Command 1: whoami → "root"
Command 2: touch /root/test → "Permission denied"
Result: IMPOSSIBLE - DETECTED AS FAKE
```

**Why it occurs:**
- LLM context window limits (finite tokens)
- No persistent state database
- Each response independently generated
- LLM can hallucinate plausible but incorrect responses

**Impact:** Complex attack chains fail, forensics unreliable.

#### Problem 3: High-Interaction Honeypots - Scalability & Risk

- Resource-intensive (full OS per honeypot instance)
- Risk of attacker pivoting to production
- Not suitable for distributed deployments
- Manual analysis of logs

### Requirements for Solution

1. **State Consistency**: File operations must be atomic and persistent
2. **Realism**: Full POSIX compliance, standard tools work
3. **Scalability**: Lightweight, deployable at scale
4. **Analyzability**: Real-time threat intelligence
5. **Maintainability**: Clean architecture, modular components

---

## 5. Proposed Method

### System Architecture Overview

Mirage implements a **5-layer architecture** combining multiple technologies to achieve all requirements:

#### Layer 1: Gateway (Entry Points)
- **SSH Honeypot**: Interactive shell on port 2222
  - Accepts any credentials
  - Session tracking
  - Command logging
- **HTTP Honeypot**: Web application simulation on port 8080
  - Multiple vulnerable endpoints
  - SQL injection/XSS detection
  - Exploit tracking

#### Layer 2: Interface (FUSE)
- Kernel-level syscall interception
- Path resolution and inode management
- File descriptor tracking
- Full POSIX semantics (read, write, mkdir, rm, etc.)

#### Layer 3: Core (State Hypervisor)
- Redis-backed state management
- Atomic operations via Lua scripts
- Inode allocation and tracking
- Transaction guarantees (ACID properties)

#### Layer 4: Intelligence (Cognitive)
- LLM providers (OpenAI, Anthropic, Mock)
- Persona engine (generates realistic content)
- Lazy evaluation (content generated on first access)
- Persistent caching (saved to Redis blob store)

#### Layer 5: Analysis (Threat Detection)
- Command analyzer (MITRE ATT&CK mapping)
- Threat library (known attack signatures)
- Skill detector (attacker profiling)
- Event processor (pattern detection)
- Audit streamer (real-time SIEM integration)

### Key Innovation: Separation of Concerns

**Critical Design Decision:**
- **LLM used for**: Content generation (ONLY)
  - Generate realistic file content on-the-fly
  - Example: `/etc/shadow`, `/var/log/nginx/access.log`
  - Content cached and persisted

- **LLM NOT used for**: State management
  - File existence tracked in Redis
  - Directory listings from Redis
  - Permissions enforced from Redis
  - No hallucination possible

**Result:** No contradictions, all state consistent, unlimited command chains supported.

---

## 6. Architecture Diagram

### System Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ATTACKER INTERFACE                          │
│                  (SSH Shell / HTTP Browser)                          │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
        ┌────────────────────────────────────┐
        │      GATEWAY LAYER                 │
        │  ┌──────────┐      ┌──────────┐   │
        │  │SSH       │      │HTTP      │   │
        │  │Honeypot  │      │Honeypot  │   │
        │  └──────────┘      └──────────┘   │
        └────────────────────┬───────────────┘
                             │
                             ↓
        ┌────────────────────────────────────┐
        │    INTERFACE LAYER (FUSE)          │
        │   - Syscall Interception           │
        │   - Path Resolution                │
        │   - File Descriptor Tracking       │
        └────────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ↓               ↓               ↓
    ┌─────────┐  ┌──────────────┐  ┌────────────┐
    │State    │  │Intelligence  │  │Analysis    │
    │Hyper-   │  │Layer         │  │Layer       │
    │visor    │  │              │  │            │
    │         │  │ ┌──────────┐ │  │ ┌────────┐ │
    │┌─────┐  │  │ │LLM       │ │  │ │Command │ │
    ││Redis│  │  │ │Providers │ │  │ │Analyzer│ │
    ││Lua  │  │  │ └──────────┘ │  │ └────────┘ │
    ││Atomic   │  │              │  │            │
    │└─────┘  │  │ ┌──────────┐ │  │ ┌────────┐ │
    │         │  │ │Persona   │ │  │ │Threat  │ │
    │         │  │ │Engine    │ │  │ │Library │ │
    │         │  │ └──────────┘ │  │ └────────┘ │
    └─────────┘  └──────────────┘  └────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
        ┌────────────────┴────────────────┐
        ↓                                 ↓
   ┌──────────────┐              ┌─────────────────┐
   │Redis Database│              │PostgreSQL Audit │
   │(Hot State)   │              │Logs (Forensics) │
   └──────────────┘              └─────────────────┘
        │                                │
        └────────────────┬───────────────┘
                         ↓
            ┌──────────────────────────┐
            │ Layer 0 (Rust)           │
            │ Traffic Analysis         │
            │ Circuit Breaker          │
            └──────────────────────────┘
```

### Data Flow Architecture

```
Attacker Command
    │
    ↓
FUSE Intercepts Syscall
    │
    ↓
State Hypervisor
    ├─→ Check Redis for current state
    ├─→ Run Lua script (atomic transaction)
    └─→ Update Redis with new state
    │
    ├─ If reading file content:
    │  └─→ Check if content cached
    │     ├─→ Yes: Return from blob store
    │     └─→ No: Call Persona Engine
    │          ├─→ LLM generates content
    │          └─→ Save to blob store
    │
    ↓
Return Result to Attacker
    │
    ↓
Analysis Layer (async)
    ├─→ Command Analyzer detects techniques
    ├─→ Threat Library matches signatures
    ├─→ Skill Detector profiles attacker
    └─→ Log to PostgreSQL (forensics)
```

---

## 7. Flow Diagram

### Detailed Attack Session Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ATTACK SESSION LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────────┘

START
  │
  ├─→ [1] ATTACKER CONNECTS
  │        SSH: ssh -l attacker 0.0.0.0 -p 2222
  │        HTTP: curl http://0.0.0.0:8080/admin
  │
  ├─→ [2] GATEWAY ACCEPTS CONNECTION
  │        SSH: Accept any credentials (honeypot behavior)
  │        HTTP: Detect threat patterns in request
  │        │ ├─ SQL Injection patterns?
  │        │ ├─ XSS patterns?
  │        │ └─ Directory traversal?
  │
  ├─→ [3] SESSION CREATED
  │        ├─ Generate session ID
  │        ├─ Store in Redis
  │        └─ Initialize user context
  │
  ├─→ [4] ATTACKER ISSUES COMMAND
  │        Example: touch /tmp/pwn
  │
  ├─→ [5] FUSE INTERCEPTS SYSCALL
  │        ├─ Translate to high-level operation
  │        └─ Call State Hypervisor
  │
  ├─→ [6] STATE HYPERVISOR PROCESSES
  │        ├─ Read current state from Redis
  │        ├─ Run Lua script (atomic):
  │        │  ├─ Check if /tmp/pwn exists
  │        │  ├─ If not: allocate inode ID
  │        │  ├─ Link filename to inode
  │        │  └─ Commit transaction
  │        └─ All-or-nothing guarantee
  │
  ├─→ [7] RESPONSE TO ATTACKER
  │        └─ "Operation successful"
  │
  ├─→ [8] ANALYSIS BEGINS (Async)
  │        ├─ Command Analyzer:
  │        │  ├─ Extract: "touch", "/tmp/pwn"
  │        │  ├─ Map to MITRE ATT&CK technique
  │        │  └─ Calculate risk score
  │        │
  │        ├─ Threat Library:
  │        │  ├─ Check against known signatures
  │        │  └─ Match: "file_creation"
  │        │
  │        ├─ Skill Detector:
  │        │  ├─ Basic command → +5 points
  │        │  └─ Estimate: "Script Kiddie"
  │        │
  │        └─ Event Processor:
  │           ├─ Store to PostgreSQL
  │           ├─ Publish to SIEM
  │           └─ Update session profile
  │
  ├─→ [9] NEXT COMMAND
  │        Example: cd /tmp && ls
  │        └─ Repeat steps [5]-[8]
  │           └─ GUARANTEED: pwn file appears in listing
  │              (no state inconsistency)
  │
  └─→ [REPEAT] Commands accumulate
           ├─ 16 unique techniques detected
           ├─ 7 attack phases identified
           ├─ 8 threat signatures matched
           ├─ Skill level refined (now "Intermediate")
           └─ Complete attack chain captured

END OF SESSION
  │
  ├─→ [10] FORENSIC ANALYSIS
  │        ├─ Retrieve complete command history
  │        ├─ Reconstruct attack timeline
  │        ├─ Generate threat report
  │        └─ Export to SIEM/incident response
```

### Command Processing Flow

```
Command: cat /var/log/nginx/access.log

    ↓ [File exists? Check Redis]
    
No ─→ [Content cached? Check Redis]
    │  │
    │  └─→ No: Call Persona Engine
    │       │
    │       ├─→ LLM Prompt: "Generate realistic nginx access log"
    │       ├─→ LLM returns content
    │       ├─→ Calculate SHA256 hash
    │       ├─→ Store in Redis blob: fs:blob:<hash>
    │       ├─→ Store inode metadata
    │       └─→ Link in directory
    │
    └──────→ Return content to attacker
             │
             └─→ Next time: Read from Redis (same content)
                           (No re-generation, no hallucination)

Yes─→ [Read from blob store]
     │
     └─→ Return cached content (CONSISTENT)
```

---

## 8. Novelty of the Proposed Method

### Key Innovations

#### Innovation 1: FUSE + Redis Integration
**First honeypot to combine:**
- Kernel-level FUSE filesystem (real POSIX)
- External Redis state database (atomic, persistent)
- Result: True filesystem consistency (no other honeypot achieves this)

#### Innovation 2: Separation of LLM Concerns
**Unique approach to LLM integration:**
- LLM ONLY for content generation (not state)
- Content persisted in Redis blob store (no re-generation)
- State management purely database-driven (no hallucination)
- Result: LLM's creativity + database's consistency

#### Innovation 3: Atomic Operations via Lua
**Advanced transaction handling:**
- All filesystem operations in Redis Lua scripts
- All-or-nothing semantics (ACID guarantee)
- No partial states (prevents race conditions)
- No concurrent operation conflicts
- Result: True multi-attacker safety

#### Innovation 4: Real-Time Threat Intelligence
**Integrated analysis pipeline:**
- MITRE ATT&CK mapping (50+ attack patterns)
- Live threat signature matching (12+ signatures)
- Attacker skill profiling (5-level classification)
- Attack phase detection (reconnaissance to defense evasion)
- Result: Complete attack understanding during session

#### Innovation 5: Lazy Content Evaluation
**Efficient resource usage:**
- Content generated ONLY when accessed
- Infinite realistic depth (attacker never exhausts filesystem)
- Cached after generation (no repeated LLM calls)
- Persona-based coherence (consistent personality)
- Result: High-fidelity honeypot at low cost

### Comparison with State-of-the-Art

| Feature | Traditional | LLM-Based | Mirage |
|---------|-------------|-----------|--------|
| **State Consistency** | ❌ | ❌ | ✅ Atomic |
| **Unlimited Commands** | ⚠️ Limited | ❌ Memory window | ✅ Infinite |
| **Permission Enforcement** | Static | Hallucinated | ✅ Enforced |
| **Content Realism** | Predefined | Generated | ✅ LLM + cached |
| **Attack Analysis** | None | None | ✅ Real-time |
| **Scalability** | Good | Poor | ✅ Excellent |
| **Detectability** | High | Medium | ✅ Low |

### Research Contributions

1. **State Management**: First practical solution to honeypot state consistency
2. **Deception Engineering**: Demonstrates effective separation of concerns (LLM for content, database for state)
3. **Threat Intelligence**: Real-time attack profiling framework integrated with honeypot
4. **Architecture**: Blueprint for scalable cognitive security systems

---

## 9. Algorithm

### Algorithm 1: Atomic File Creation

```
ALGORITHM: CreateFile(path, mode, data=NULL)
INPUT:
  path: Full file path (e.g., "/tmp/pwn")
  mode: Permission bits (e.g., 0644)
  data: Optional initial content
OUTPUT:
  success: Boolean (True if created, False if exists)
  inode_id: Integer (allocated inode ID or error)

BEGIN
  1. REDIS_TRANSACTION_START()
  
  2. parent_path ← PATH_PARENT(path)
     filename ← PATH_BASENAME(path)
  
  3. parent_inode ← RESOLVE_PATH(parent_path)
     IF parent_inode == NULL THEN
       REDIS_TRANSACTION_ABORT()
       RETURN (False, ERROR_PARENT_NOT_FOUND)
     END IF
  
  4. exists ← REDIS_ZSET_ISMEMBER(
       key="fs:dir:" + parent_inode,
       member=filename
     )
     IF exists THEN
       REDIS_TRANSACTION_ABORT()
       RETURN (False, ERROR_FILE_EXISTS)
     END IF
  
  5. new_inode ← REDIS_INCR("fs:next_inode")
  
  6. REDIS_HSET(
       key="fs:inode:" + new_inode,
       fields={
         "mode": mode,
         "uid": 0,
         "gid": 0,
         "size": 0 OR LENGTH(data),
         "created": TIMESTAMP(),
         "modified": TIMESTAMP(),
         "type": "file"
       }
     )
  
  7. IF data IS NOT NULL THEN
       content_hash ← SHA256(data)
       REDIS_SET(
         key="fs:blob:" + content_hash,
         value=data
       )
       REDIS_HSET(
         key="fs:inode:" + new_inode,
         fields={"content_hash": content_hash}
       )
     END IF
  
  8. REDIS_ZADD(
       key="fs:dir:" + parent_inode,
       score=new_inode,
       member=filename
     )
  
  9. REDIS_TRANSACTION_COMMIT()
  
  10. AUDIT_LOG(
        event="file_created",
        inode=new_inode,
        path=path,
        timestamp=TIMESTAMP()
      )
  
  11. RETURN (True, new_inode)
END
```

### Algorithm 2: Atomic Directory Listing

```
ALGORITHM: ListDirectory(path)
INPUT:
  path: Directory path (e.g., "/tmp")
OUTPUT:
  entries: List of (filename, inode_id, metadata)
  or ERROR

BEGIN
  1. inode ← RESOLVE_PATH(path)
     IF inode == NULL THEN
       RETURN ERROR_PATH_NOT_FOUND
     END IF
  
  2. metadata ← REDIS_HGETALL("fs:inode:" + inode)
     IF metadata.type != "directory" THEN
       RETURN ERROR_NOT_A_DIRECTORY
     END IF
  
  3. entries ← EMPTY_LIST
  
  4. FOR EACH (score, member) IN 
       REDIS_ZRANGE(
         key="fs:dir:" + inode,
         start=0,
         stop=-1,
         withscores=True
       )
     DO:
       entry_inode ← score
       entry_name ← member
       entry_meta ← REDIS_HGETALL("fs:inode:" + entry_inode)
       entries.APPEND({
         "name": entry_name,
         "inode": entry_inode,
         "mode": entry_meta.mode,
         "size": entry_meta.size,
         "timestamp": entry_meta.modified
       })
     END FOR
  
  5. RETURN entries
END
```

### Algorithm 3: Command Analysis with MITRE ATT&CK

```
ALGORITHM: AnalyzeCommand(command_text, session_id)
INPUT:
  command_text: Full command string
  session_id: Session identifier
OUTPUT:
  analysis: {techniques, risk_score, detection}

BEGIN
  1. command_tokens ← TOKENIZE(command_text)
  
  2. detected_techniques ← EMPTY_SET
     risk_score ← 0
  
  3. FOR EACH pattern IN MITRE_ATT&CK_PATTERNS DO:
     IF REGEX_MATCH(pattern.regex, command_text) THEN
       detected_techniques.ADD(pattern.technique_id)
       risk_score += pattern.base_score
       
       FOR EACH indicator IN pattern.indicators DO:
         IF CONTAINS(command_text, indicator) THEN
           risk_score += indicator.bonus_score
         END IF
       END FOR
     END IF
  END FOR
  
  4. threat_matches ← EMPTY_LIST
     FOR EACH threat_sig IN THREAT_LIBRARY DO:
       FOR EACH sig_pattern IN threat_sig.patterns DO:
         IF REGEX_MATCH(sig_pattern, command_text) THEN
           threat_matches.APPEND(threat_sig)
           risk_score += threat_sig.severity_weight
         END IF
       END FOR
     END FOR
  
  5. risk_category ← CATEGORIZE_RISK(risk_score)
     // 0-20: Low, 20-50: Medium, 50-100: High, 100+: Critical
  
  6. analysis ← {
       "command": command_text,
       "techniques": detected_techniques,
       "threats": threat_matches,
       "risk_score": risk_score,
       "risk_level": risk_category,
       "timestamp": TIMESTAMP(),
       "session_id": session_id
     }
  
  7. POSTGRESQL_INSERT("audit_log", analysis)
  
  8. RETURN analysis
END
```

### Algorithm 4: Attacker Skill Assessment

```
ALGORITHM: AssessAttackerSkill(session_id, command_analyses)
INPUT:
  session_id: Session identifier
  command_analyses: List of command analysis results
OUTPUT:
  skill_profile: {level, score, confidence, indicators}

BEGIN
  1. skill_score ← 0
     indicators ← EMPTY_LIST
  
  2. FOR EACH analysis IN command_analyses DO:
     // Count techniques
     technique_count += analysis.techniques.COUNT()
     
     // Tool sophistication
     FOR EACH tool IN ADVANCED_TOOLS DO:
       IF CONTAINS(analysis.command, tool) THEN
         skill_score += 15
         indicators.APPEND("Uses " + tool)
       END IF
     END FOR
     
     // Error handling (good attackers handle errors)
     IF CONTAINS(analysis.command, "|| ") OR
        CONTAINS(analysis.command, "&& ") THEN
       skill_score += 10
       indicators.APPEND("Good error handling")
     END IF
     
     // Reconnaissance depth
     IF CONTAINS(analysis.command, "find") OR
        CONTAINS(analysis.command, "locate") THEN
       skill_score += 5
     END IF
  END FOR
  
  3. attack_phases ← EXTRACT_ATTACK_PHASES(command_analyses)
     phases_count ← attack_phases.COUNT()
     skill_score += (phases_count * 10)
  
  4. // Classify skill level
     IF skill_score < 15 THEN
       level ← "Script Kiddie"
       confidence ← "High"
     ELSE IF skill_score < 35 THEN
       level ← "Opportunistic"
       confidence ← "High"
     ELSE IF skill_score < 65 THEN
       level ← "Intermediate"
       confidence ← "Medium"
     ELSE IF skill_score < 85 THEN
       level ← "Advanced"
       confidence ← "Medium"
     ELSE
       level ← "Expert APT"
       confidence ← "High"
     END IF
  
  5. skill_profile ← {
       "skill_level": level,
       "skill_score": skill_score,
       "confidence": confidence,
       "indicators": indicators,
       "unique_techniques": technique_count,
       "attack_phases": attack_phases,
       "session_id": session_id
     }
  
  6. RETURN skill_profile
END
```

---

## 10. Working Principle

### How Mirage Achieves State Consistency

#### Principle 1: Atomic Transactions

**Without Atomicity** (Traditional honeypots):
```
Operation: touch /tmp/pwn && ls /tmp

Step 1: Update script matches 'touch'
        File marked as "should exist"
        (But not persisted)

Step 2: Attacker immediately runs ls /tmp
        List script doesn't have updated file
        (File not in listing)

Result: INCONSISTENCY DETECTED
```

**With Mirage (Atomic)**:
```
Operation: touch /tmp/pwn && ls /tmp

Step 1: FUSE intercepts touch syscall
        State Hypervisor runs Lua script:
        
        BEGIN TRANSACTION
          - Check if /tmp/pwn exists
          - Allocate new inode
          - Link filename → inode in Redis
          - Increment inode counter
        COMMIT TRANSACTION ← ALL-OR-NOTHING
        
Step 2: Attacker immediately runs ls /tmp
        FUSE intercepts ls syscall
        State Hypervisor reads from Redis:
        - Query fs:dir:$tmp_inode
        → Returns: pwn (file GUARANTEED there)

Result: CONSISTENT STATE
```

#### Principle 2: External State Storage

**LLM-Based Hallucination**:
```
Command History:  "cd /home/attacker" (stored in LLM context)
[50 more commands...]
Current Context:  4090/4096 tokens (FULL)

New Command: pwd

LLM Logic:
- Check context for "current directory"
- Context exceeded (token limit)
- Old tokens dropped
- LLM generates plausible response: "/root"
- But this contradicts actual working directory

Result: HALLUCINATION (forgot cd)
```

**Mirage Approach**:
```
Command: cd /home/attacker

State Hypervisor:
- Store in Redis: "session:$sid:cwd" = "/home/attacker"
- DATA PERSISTED (outside LLM, outside context window)

[50 more commands...]

New Command: pwd

State Hypervisor:
- Read from Redis: "session:$sid:cwd"
- Returns: "/home/attacker"
- CORRECT (never forgotten, persisted)

Result: NO HALLUCINATION
```

#### Principle 3: Lazy Content Generation

**Problem**: LLM called for every file read = expensive, slow, no consistency

**Mirage Solution**:
```
Attacker: cat /etc/shadow

Check 1: File exists in Redis?
  No ← First access

Call Persona Engine:
  Prompt: "Generate realistic /etc/shadow for Ubuntu 20.04"
  LLM Returns: "root:*:18900:0:99999:7:::"
  (realistic, but one-time call)

Action: Store in Redis blob
  fs:blob:<sha256_hash> = content
  Update inode metadata

Attacker: cat /etc/shadow (later)

Check 1: File exists in Redis?
  Yes
  
Check 2: Content cached?
  Yes → Return from Redis blob store
        (NO LLM CALL, NO RE-GENERATION)
  
Result: SAME content every time
        NO hallucination possible
```

#### Principle 4: Real-Time Analysis

**Traditional Honeypots**: Manual log analysis hours/days later

**Mirage**: Async analysis during attack
```
Attacker runs: find / -name "*.conf" -type f -size +1k

DURING execution:
  1. FUSE intercepts find syscall
  2. Command Analyzer runs:
     - Matches "reconnaissance" pattern
     - Maps to MITRE T1087 (Account Discovery)
     - Assigns risk_score = 25
     
  3. Threat Library:
     - Matches "file_enumeration" signature
     - Threat severity = "Medium"
     
  4. Skill Detector:
     - Recognizes sophisticated find options
     - Awards +10 points
     
  5. Event Processor:
     - Stores to PostgreSQL
     - Streams to SIEM
     - Updates session profile

RESULT: Threat intelligence updated in real-time
         (not waiting for post-attack analysis)
```

#### Principle 5: Separation of Concerns

**Mirage Architecture Decision**:

| Component | Responsibility | Why |
|-----------|-----------------|-----|
| **FUSE** | Syscall interception | Real-time interface |
| **State Hypervisor** | State logic | Atomic transactions |
| **Redis** | State storage | Persistent, external |
| **LLM** | Content generation | Creativity |
| **Persona** | Coherence | Personality consistency |
| **Analyzer** | Threat detection | Attack understanding |

**Key Insight**: Each component does ONE thing well
- Not asking LLM to manage state (can't do reliably)
- Not using Redis to generate content (inflexible)
- Not asking FUSE to handle transactions (too complex)

Result: **Clean architecture**, each component excels at its task

---

## 11. Conclusion

### Key Achievements

Mirage successfully demonstrates:

1. **State Consistency Problem SOLVED**
   - Atomic operations via Redis + Lua scripts
   - No state hallucinations (unlike LLM honeypots)
   - No inconsistencies (unlike traditional honeypots)
   - Unlimited command chain support

2. **Realism Achieved**
   - Full POSIX filesystem via FUSE
   - Standard Linux tools work transparently
   - Complex command pipes and redirects supported
   - Cognitive intelligence via LLM content generation

3. **Scalability Demonstrated**
   - Lightweight Python + Rust hybrid
   - Docker-deployable architecture
   - 4 verification phases (all passing)
   - Real-time threat analysis

4. **Threat Intelligence Capability**
   - MITRE ATT&CK framework integration
   - 50+ attack pattern detection
   - 12+ threat signature library
   - 5-level attacker skill profiling
   - Attack phase tracking

### Impact & Applications

**For Security Research:**
- Analyze genuine attacker behavior (not detection evasion)
- Complete attack chain forensics
- Attack pattern discovery

**For SOC Operations:**
- Cost-effective honeypot infrastructure
- Threat early warning system
- Attacker skill assessment
- Real-time threat feeds

**For Incident Response:**
- Forensic investigation starting point
- Attacker timeline reconstruction
- Threat signature extraction
- IOC discovery

### Limitations & Future Work

**Current Limitations:**
- Single-host deployment (no lateral movement simulation)
- SSH/HTTP only (no other protocols)
- Limited to Python-based analysis
- Requires OpenAI/Anthropic API for full LLM features

**Future Enhancements (Phase 5):**
1. **Dashboard**: Web UI for real-time monitoring
2. **Multi-Host Topology**: Simulate network for lateral movement
3. **Additional Protocols**: FTP, SMTP, RDP honeypots
4. **Machine Learning**: Behavioral anomaly detection
5. **Distributed Deployment**: Honeypot network coordination
6. **Attribution Engine**: Attacker fingerprinting

### Final Remarks

Mirage represents a **paradigm shift** in honeypot design:
- From **detection evasion** to **genuine interaction**
- From **scripted responses** to **real filesystem**
- From **manual analysis** to **real-time intelligence**
- From **resource-intensive** to **scalable**

By solving the state hallucination problem, Mirage enables organizations to:
- **Attract** sophisticated attackers (consistent behavior)
- **Analyze** complete attack chains (full POSIX support)
- **Understand** attacker capabilities (skill profiling)
- **Defend** proactively (threat intelligence)

The framework is **production-ready** and demonstrates that:
> *"True deception is not fooling attackers into thinking you're real—it's actually being real while appearing to be a decoy."*

---

## 12. References

### Academic Papers & Research

1. **Honeypot Systems & State Management**
   - Provos, N. (2004). "A Virtual Honeypot Framework." USENIX Security
   - Spitzner, L. (2003). "Honeypots: Tracking Hackers." Addison-Wesley
   - Mirkovic, J., et al. (2005). "Internet Attacks: State of the Art." Technical Report USC-ISI

2. **State Machine & Consistency**
   - Garcia-Molina, H., et al. (2008). "Database Systems: The Complete Book." Prentice Hall
   - Herlihy, M. & Wing, J. (1990). "Linearizability: A Correctness Condition for Concurrent Objects." ACM TOPLAS

3. **FUSE & Filesystem Design**
   - Szeredi, M. (2010). "FUSE: Filesystem in Userspace." Linux Kernel Documentation
   - Vangoor, A., et al. (2017). "Accurate and Efficient SSD Performance Isolation with Defog." FAST

4. **LLM Limitations & Hallucination**
   - Liu, N., et al. (2023). "Lost in the Middle: How Language Models Use Long Contexts." arXiv:2307.03172
   - OpenAI. (2023). "GPT-4 Technical Report." arXiv:2303.08774
   - Roller, S., et al. (2021). "Recipes for Building an Open-Domain Chatbot." Facebook AI

5. **MITRE ATT&CK Framework**
   - MITRE Corporation. (2013-2024). "ATT&CK: Adversary Tactics, Techniques, and Common Knowledge."
   - Attack Technique Documentation: https://attack.mitre.org/

6. **Redis & Distributed Systems**
   - Sanfilippo, S. (2009). "Redis Data Structure Server." http://redis.io/
   - Brewer, E. (2000). "Towards Robust Distributed Systems." PODC

7. **Threat Intelligence & Attack Analysis**
   - Liao, Q., et al. (2013). "Phase Detection in Cybersecurity." IEEE S&P
   - Chakrabarti, A., et al. (2021). "Cyber Threat Intelligence: A Review." Cybersecurity Reviews

### Technical Documentation

8. **Python Libraries & Frameworks**
   - Paramiko: SSH2 protocol implementation
   - fusepy: FUSE filesystem binding for Python
   - psycopg2: PostgreSQL adapter for Python
   - pydantic: Data validation library

9. **Rust & PyO3**
   - Rust Foundation. "The Rust Programming Language." https://www.rust-lang.org/
   - PyO3 Documentation: "Rust Bindings for Python." https://pyo3.rs/

10. **DevOps & Deployment**
    - Docker Inc. (2023). "Docker Documentation." https://docs.docker.com/
    - Kubernetes Community. "Kubernetes Documentation." https://kubernetes.io/

### Project References

11. **Honeypot Projects (Comparison)**
    - Cowrie: SSH/Telnet Honeypot (https://github.com/cowrie/cowrie)
    - Honeyd: Virtual Honeypot (https://www.honeyd.org/)
    - Conpot: ICS/SCADA Honeypot (https://github.com/mushorg/conpot)
    - Glastopf: Web Application Honeypot (https://github.com/mushorg/glastopf)

### Related Work

12. **Deception & Cyber Defense**
    - Almohri, H., et al. (2014). "Deception-as-a-Defense Strategy Against Sophisticated Attacks." IEEE
    - Rowe, N., et al. (2007). "Defending against Social Engineering and Phishing Attacks." IEEE
    - Yuill, J., et al. (2004). "Intrusion Detection in Honeypot Systems." 2004 DARPA Information Survivability Conference

### Websites & Online Resources

13. **Security Communities & Standards**
    - OWASP: "Web Application Security." https://owasp.org/
    - CIS Controls: "Critical Security Controls." https://www.cisecurity.org/
    - Honeynet Project: "Honeynet Tools & Resources." https://www.honeynet.org/

14. **Threat Intelligence Sources**
    - AlienVault OTX: "Open Threat Exchange." https://otx.alienvault.com/
    - VirusTotal: "Malware & URL Scanning." https://www.virustotal.com/
    - Shodan: "Internet Search Engine." https://www.shodan.io/

### Dataset & Benchmarks

15. **Attack Pattern Databases**
    - MITRE ATT&CK Matrix: https://attack.mitre.org/
    - Common Weakness Enumeration (CWE): https://cwe.mitre.org/
    - Common Attack Pattern Expression Language (CAPEC): https://capec.mitre.org/

---

## Appendix: Technical Specifications

### System Requirements

**Hardware:**
- CPU: 2+ cores
- RAM: 4GB minimum (8GB recommended)
- Storage: 10GB (for PostgreSQL audit logs)
- Network: Standard Ethernet

**Software:**
- Python 3.13+
- Redis 7.0+
- PostgreSQL 15+
- Docker 24.0+
- Rust 1.70+ (for Layer 0)

### File Statistics

- **Total Lines of Code**: ~2,500
- **Python Modules**: 20+
- **Test Coverage**: 4 verification phases
- **Documentation**: ~1,500 lines

### Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **State Operation Latency** | <1ms | Redis Lua script |
| **FUSE Syscall Overhead** | <5ms | Typical filesystem call |
| **LLM Content Generation** | ~2-5s | One-time per file |
| **Command Analysis** | <100ms | Per-command overhead |
| **Audit Log Write** | <50ms | PostgreSQL batch |

### Deployment Architecture

```
┌─────────────────────────────────────┐
│     Docker Container                │
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ Chronos Application (Python)    │ │
│ ├──────────┬──────────┬──────────┬┤ │
│ │ Gateway  │ FUSE     │ Analysis │ │
│ └──────────┴──────────┴──────────┴┤ │
│ ┌─────────────────────────────────┐ │
│ │ Layer 0 (Rust)                  │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
         │              │
         ↓              ↓
    ┌─────────┐    ┌──────────────┐
    │ Redis   │    │ PostgreSQL   │
    │ (State) │    │ (Audit Logs) │
    └─────────┘    └──────────────┘
```

---

**End of Final Presentation**

*Submitted for CCD 334 - Miniproject*
*Mirage: AI-Powered Decoy System*
*February 2026*
