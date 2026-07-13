# Chronos AI Logic Reference

**Purpose:** Concrete algorithms, schemas, and decision rules for the AI integration.
This is the "how it decides" document — `AI_ARCHITECTURE.md` covers "how it's wired."

**Core constraint:** AI is restricted to Ubuntu 24.04 artifact generation only.
No other OS, device type, or cloud provider is supported or anticipated.

---

## 1. Ubuntu Profile Schema

Replaces the old multi-persona YAML system. There is exactly one file.

**File:** `config/ubuntu.yaml`

```yaml
ubuntu_version: "24.04"
codename: "noble"
kernel_version: "6.8.0-51-generic"
hostname: "web01"
primary_user: "ubuntu"
timezone: "UTC"

installed_packages:
 - { name: nginx,      version: "1.24.0" }
 - { name: openssh-server, version: "9.6p1" }
 - { name: fail2ban,    version: "1.0.2" }

running_services: [nginx, ssh, cron, ufw, fail2ban]
open_ports:
 - { port: 22, proto: tcp, service: ssh }
 - { port: 80, proto: tcp, service: nginx }

users:
 - { name: ubuntu, uid: 1000, shell: /bin/bash }
 - { name: www-data, uid: 33, shell: /usr/sbin/nologin }

ssh_config:
 permit_root_login: false
 password_authentication: true

cron_jobs:
 - { user: root, schedule: "0 2 * * *", command: "/usr/bin/certbot renew --quiet" }

filesystem_layout:
 - /etc/nginx/
 - /etc/ssh/
 - /var/log/nginx/
 - /home/ubuntu/
```

**Loader behavior (`UbuntuProfile`):**
- Loaded once at startup from `config/ubuntu.yaml`.
- On missing file: logs warning, uses minimal safe default. Does not crash.
- `get_or_create_machine_state(redis, session_id)` creates the Redis hash on first access and freezes it for the session duration.
- AI cannot modify MachineState — it only reads the relevant subgraph.

---

## 2. Artifact Policy Resolution

Runs before any AI call. The policy determines what the AI will generate, not the other way around.

**File:** `config/generation_policy.yaml`

```yaml
artifact_policy:
 credential_file:
  distribution: { useful: 0.05, empty: 0.40, abandoned: 0.30, notes: 0.20, corrupted: 0.05 }
  max_lines: 20
  validation_strictness: high
  regeneration: static

 config_file:
  distribution: { valid: 0.90, deprecated: 0.08, broken: 0.02 }
  max_lines: 80
  validation_strictness: high
  regeneration: static

 log_file:
  distribution: { active: 0.70, archived: 0.20, empty: 0.05, corrupted: 0.05 }
  max_lines: 500
  max_days: 7
  validation_strictness: medium
  regeneration: dynamic

 history_file:
  distribution: { active: 0.75, empty: 0.15, abandoned: 0.10 }
  max_entries: 300
  validation_strictness: low
  regeneration: dynamic

model_routing:
 history_file:  "llama3:3b"
 notes_file:   "llama3:3b"
 temp_file:    "llama3:3b"
 config_file:   "llama3:8b"
 script_file:   "llama3:8b"
 log_file:    "llama3:8b"
 credential_file: "llama3:8b"
 default:     "llama3:8b"
```

**Decision flow — ArtifactPolicyEngine.resolve(filename, path):**
```
1. infer_file_class(filename, path)
  → applies ordered rules: credential patterns → history → log → config → script → notes → temp
  → returns a file class string

2. Lookup class policy in generation_policy.yaml

3. Sample category from probability distribution (weighted random)
  e.g., config_file → {valid: 0.90, deprecated: 0.08, broken: 0.02}
  → category = "valid" (90% probability)

4. If category == "empty": skip_generation = True → return b'' immediately, no AI call

5. Return ArtifactPolicy(file_class, category, max_lines, model, validation_strictness, …)
```

**Attacker skill level does NOT influence model routing.**
Skill → monitoring and evidence collection only.
Model routing depends solely on file class (reproducible, verifiable behavior).

---

## 3. Non-Blocking Generation & Adaptive Timeouts

**State per inode during generation:** Redis key `fs:generating:<inode>` (TTL 30s)
acts as a distributed lock preventing duplicate generation from concurrent FUSE threads.

**Decision flow for `read()` on a cache-miss:**
```
1. content_hash present in fs:inode:<id>?
  YES → return cached blob immediately (fast path, no AI involved)
  NO → check inference quota for session_id (token bucket in Redis)
     if quota exceeded → return static_template_for(file_class)

2. Is generation already in-flight for this inode?
  YES → attach to existing future
  NO → acquire Redis lock; submit new GenerationOrchestrator task

3. Calculate Adaptive Timeout:
  timeout = p95_latency(model_id) + 2.0s
  (rolling 50-sample window in Redis; falls back to 10.0s if insufficient history)

4. Wait up to `timeout` on the future.
  COMPLETED → validate (§4) → persist → return content
  TIMEOUT  → do NOT cancel the future; let it keep running
       → return random.choice([errno.EAGAIN, errno.ETIMEDOUT, errno.EIO])
       → log timeout event with inode/file_class/model tags

5. On future completion (whether or not anyone was waiting):
  → validate (§4)
  → persist content blob, inode content_hash, blob_meta provenance
  → release fs:generating:<inode> lock
```

---

## 4. Predictive Generation Triggers & Priorities

Two fire-and-forget trigger points (submitted to the same background pool):

**Trigger A — on `create()`:**
```
create(path, mode):
  inode = allocate_inode(parent_inode, name)
  submit_background(generate_and_persist, inode, path, session_id, PRIORITY_HIGH)
```

**Trigger B — on `readdir()`, bounded:**
```
readdir(path, fh):
  children = redis.zrange(f"fs:dir:{inode}", 0, -1)

  prewarm_count = 0
  for name in children:
    if prewarm_count >= PREWARM_LIMIT: # = 5
      break
    child_inode = lookup(inode, name)
    if not has_content_hash(child_inode):
      submit_background(generate_and_persist, child_inode, path/name, session_id, PRIORITY_MEDIUM)
      prewarm_count += 1

  return ['.', '..'] + children
```

**Prioritization:** `prewarm_priorities` in `generation_policy.yaml` lists file classes
in order of expected attacker interest (credential_file first, temp_file last).

---

## 5. Semantic Output Validation

Runs after generation, before persistence. Cross-references generated content against MachineState.

**Four-tier validation:**
```
validate(content, policy, machine_state):

  # Tier 1: Refusal boilerplate (always)
  if any(pattern.search(content) for pattern in REFUSAL_PATTERNS):
    return REJECT("refusal_boilerplate")
  # Patterns include: "As an AI", "I cannot generate", "```", "Here is the..."

  # Tier 2: Ubuntu conventions (always)
  if any(non_ubuntu_marker in content.lower() for marker in ["windows", "powershell", "C:\\", "yum", "dnf", "zypper"]):
    return REJECT("ubuntu_convention")

  # Tier 3: MachineState contradictions (medium + high strictness)
  if policy.validation_strictness in ("medium", "high"):
    for daemon, package in DAEMON_PACKAGE_MAP.items():
      if daemon in content and package not in installed_packages:
        return REJECT(f"contradiction: {daemon} references {package} which is not installed")

  # Tier 4: Information density (high strictness only)
  if policy.validation_strictness == "high":
    if len(content.splitlines()) > policy.max_lines:
      return REJECT(f"density: {line_count} lines exceeds max_lines={policy.max_lines}")

  return ACCEPT

on generation complete:
  result = validate(content, policy, machine_state)
  if result == ACCEPT:
    persist(content)
  else:
    retry_count += 1
    if retry_count < 2:
      regenerate()
    else:
      persist(static_template_for(file_class)) # minimal, Ubuntu-plausible
```

---

## 6. Prompt Builder

**Template structure:**
```
Generate '{filename}' located at '{path}'.

=== CONSTRAINTS ===
- Ubuntu {ubuntu_version} (kernel {kernel_version})
- Maximum {max_lines} lines.
- Artifact category: {category} — {category_instruction}
- Do NOT invent any facts not present in the Machine State block below.
- Output ONLY the raw file content. No markdown fences. No preamble.

=== MACHINE STATE ===
{relevant_facts_subgraph}

=== OUTPUT ===
(Begin file content immediately below this line)
```

**System prompt (scopes model to Ubuntu only):**
```
You are generating filesystem artifacts for a real Ubuntu {version} server
named '{hostname}'. The primary user is '{user}'.
You only generate content that would genuinely exist on Ubuntu {version}.
Never generate content for Windows, macOS, or other operating systems.
Never explain what you are doing. Output only file content.
```

**Relevant subgraph selection (reduces context waste and contradiction risk):**
```
RELEVANT_FIELDS = {
  "config_file":   ["ubuntu_version", "kernel_version", "hostname",
            "installed_packages", "running_services", "open_ports", "ssh_config"],
  "credential_file": ["ubuntu_version", "users", "groups", "primary_user"],
  "log_file":    ["ubuntu_version", "hostname", "running_services", "open_ports"],
  "history_file":  ["ubuntu_version", "primary_user", "installed_packages", "running_services"],
  "script_file":   ["ubuntu_version", "installed_packages", "running_services", "primary_user"],
  "notes_file":   ["primary_user"],
  "temp_file":    ["running_services", "open_ports"],
}
```

**Prompt injection hardening:**
1. Sanitize `filename`/`path`: strip all characters not in `[a-zA-Z0-9/._-]`, truncate to 120 chars.
2. Wrap attacker-influenced data in clearly-delimited Machine State block.
3. Filename/path content never modifies MachineState.
4. Validator (§5) catches refusal boilerplate if model bypasses constraints.

---

## 7. Provenance Metadata

Every persisted blob has a corresponding provenance record:

```
fs:blob_meta:<sha256_hash> = {
  "ubuntu_version":    "24.04",
  "kernel_version":    "6.8.0-51-generic",
  "model":         "llama3:8b",
  "file_class":      "config_file",
  "category":       "valid",
  "validation_strictness": "high",
  "generated_at":     <unix timestamp>,
  "validated":       "true"
}
```

Note: There is no `persona` field. There is no `fidelity_tier` field.
Those concepts have been removed. Ubuntu version + model + file class + category
is sufficient to reproduce any generated artifact.

---

## 8. Inference Quota

Per-session quota prevents resource exhaustion from `find /` or similar mass-read operations:

```
check_and_decrement_quota(session_id):
  bucket_key = f"chronos:quota:{session_id}:{int(time.time() // 60)}"
  count = redis.incr(bucket_key)
  redis.expire(bucket_key, 120)

  if count > MAX_GENERATIONS_PER_MINUTE: # default: 20
    return QUOTA_EXHAUSTED → use static_template_for(file_class)
  return ALLOWED
```

On quota exhaustion: serve static minimal Ubuntu-plausible content, never an error message.
Quota resets automatically on next 60-second window.
