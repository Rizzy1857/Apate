# Chronos AI Logic Reference

**Purpose:** Concrete algorithms, schemas, and decision rules for the AI
integration work described in `AI_ROADMAP.md`. This is the "how it decides"
document — `AI_ARCHITECTURE.md` covers "how it's wired."

---

## 1. Persona Configuration Schema

Replaces the hardcoded dict in `PersonaEngine._load_personas()`.

**File layout:**
```
config/personas/
  ubuntu_server.yaml
  vulnerable_db.yaml
  iot_device.yaml
```

**Schema (per file):**
```yaml
id: vulnerable_db
system_prompt: >
  You are a legacy PostgreSQL database server with weak configurations.
  You are running on Debian 10.
traits: [vulnerable, slow]

# Used by MachineState and Relationship Engine (see §5)
machine_state_schema:
  - hostname
  - primary_user
  - os_version
  - ip_address
  - db_version
  - listening_ports

# Used by fidelity coupling (see §7)
default_fidelity: cheap_model

# Used by semantic validation gate (see §4)
content_types:
  - config
  - log
  - credential_file
```

**Loader behavior:**
- `PersonaEngine._load_personas()` glob-loads `config/personas/*.yaml` at
  startup.
- Invalid YAML for one persona logs a warning and skips that file — it must
  not crash startup (matches "fail boringly" philosophy from Layer 0).

---

## 2. Non-Blocking Generation & Adaptive Timeouts

**State per inode during generation:** a Redis key
`fs:generating:<inode>` (TTL 30s) acts as a distributed lock so concurrent
reads from multiple FUSE worker threads don't trigger duplicate generation.

**Decision flow for `read()` on a cache-miss:**

```
1. content_hash present in fs:inode:<id>?
   YES -> return cached blob immediately (fast path, no LLM involved)
   NO  -> check inference quota for current session
          if quota exceeded -> return template_only

2. Is a generation already in-flight for this inode?
   YES -> attach to existing future
   NO  -> submit new generation task to background pool, acquire Redis lock

3. Calculate Adaptive Timeout:
   timeout = p95_latency(model_id) + safety_margin(2.0s)

4. Wait up to `timeout` on the future.
   COMPLETED in time -> validate (see §4) -> persist -> return content
   TIMEOUT            -> do NOT cancel the future; let it keep running
                        -> return a randomized realistic POSIX error
                             random.choice([errno.EAGAIN, errno.ETIMEDOUT, errno.EIO])
                        -> log timeout event with inode/persona/model tags

5. On future completion (whether or not anyone was still waiting):
   -> validate (see §4)
   -> persist content_hash to fs:inode:<id>
   -> release fs:generating:<inode> lock
```

**Adaptive Timeouts:** Different models have different latencies. A CPU-bound 8b parameter model takes longer than a GPU-bound 3b parameter model. The timeout is dynamically calculated based on rolling historical latency data per model.

---

## 3. Predictive Generation Triggers & Priorities

Two trigger points, both fire-and-forget (submit to the same background
pool used in §2, don't block the calling syscall):

**Trigger A — on `create()`:**
```
create(path, mode):
    inode = lookup(parent_inode, name)
    submit_background(generate_and_persist, inode, path, priority=HIGH)
```

**Trigger B — on `readdir()`, bounded and prioritized:**
```
readdir(path, fh):
    children = redis.zrange(f"fs:dir:{inode}", 0, -1)
    
    # Priority sorting: Likely Reads > Frequently Accessed > Common > Rest
    sorted_children = prioritize_predictive_reads(children)
    
    for name in sorted_children[:PREWARM_LIMIT]:
        child_inode = lookup(inode, name)
        if not has_content_hash(child_inode):
            submit_background(generate_and_persist, child_inode, path/name, priority=MEDIUM)
    return ['.', '..'] + children
```

**Prioritization Logic:** Prewarming everything wastes compute. The system prioritizes generation based on known attacker behavior (e.g., `/etc/passwd`, `.bash_history` get prewarmed before `/etc/apt/apt.conf`).

---

## 4. Semantic Output Validation / Anti-Slop Gate

Runs after generation, before persistence. Unlike structural validation, this cross-references against the `MachineState`.

**Flow:**
```
validate_semantically(content, content_type, machine_state):
    if refusal_boilerplate_detected(content):
        return REJECT
        
    if content_type == 'config':
        if references_impossible_version(content, machine_state.os_version):
            return REJECT
        if enables_nonexistent_service(content, machine_state.listening_ports):
            return REJECT
            
    return ACCEPT

on generation complete:
    result = validate_semantically(content, type, session_state)
    if result == ACCEPT:
        persist(content)
    else:
        retry_count += 1
        if retry_count < 2:
            regenerate()
        else:
            persist(static_template_for(content_type))
```

---

## 5. MachineState & Relationship Engine

**Problem being solved:** Two ghost files generated independently in the
same session must agree on facts. Moreover, facts are not flat; they have dependencies.

**Storage:** `chronos:machine_state:<session_id>` — a Relational JSON object.

**Establishment via Relationship Engine:**
```
get_or_create_machine_state(session_id, persona):
    existing = redis.hgetall(f"chronos:machine_state:{session_id}")
    if existing: return existing

    # The Relationship Engine infers dependencies automatically
    state = generate_base_state(persona)
    
    # Example Inference:
    # Apache Installed -> Port 80 Open -> Apache Logs Exist -> systemctl apache2 works
    state = infer_dependencies(state)
    
    redis.hset(f"chronos:machine_state:{session_id}", mapping=state)
    return state
```

**Injection via Prompt Builder:**
```
prompt_builder(filename, path, machine_state, persona):
    # Only include relevant facts to save prompt budget
    relevant_facts = extract_relevant_subgraph(machine_state, filename)
    
    prompt = (
        f"Context Model:\n{relevant_facts}\n\n"
        f"Generate file '{filename}'. Obey the Context Model."
    )
    return prompt
```

---

## 6. Task Routing & Inference Budgeting

Not all files require a 70B parameter model. Tasks are routed based on complexity to conserve compute.

**Routing Logic:**
```
route_task(filename, content_type):
    if filename in STATIC_TEMPLATES:
        return 'template'
    elif content_type in ['history', 'tiny_log']:
        return 'llama3:3b'  # Tiny, fast
    elif content_type == 'config':
        return 'llama3:8b'  # Medium
    elif content_type == 'sql_dump':
        return 'mixtral:8x7b' # Large
```

**Inference Quotas:** 
Each session gets a budget (e.g., 20 generations per minute). Once exhausted, the `Model Router` automatically routes to `template` until the bucket refills.

---

## 7. Dynamic File Versioning

**Problem:** Static generated files look suspicious to attackers. Logs and histories should evolve.

**Versioning Logic:**
```
persist(content, content_type):
    if content_type in ['log', 'history', 'cache']:
        # Store as an appendable list or versioned blob
        append_to_dynamic_blob(content_hash, content)
        schedule_world_evolution_tick()
    else:
        # Configs remain immutable
        freeze_blob(content_hash, content)
```

**World Evolution (Future):** A background tick that periodically appends to logs, bumps uptime, and adds temporary files.

---

## 8. Provenance Metadata

**Storage:** parallel hash next to each blob.
```
fs:blob_meta:<hash> = {
    "persona":        "vulnerable_db",
    "model":          "llama3:8b",
    "prompt_version": "<hash of prompt template>",
    "seed":           1048291,
    "temperature":    0.7,
    "top_p":          0.9,
    "fidelity_tier":  "cheap_model",
    "generated_at":   <unix timestamp>,
    "validated":      true
}
```

---

## 9. Prompt-Injection Hardening

**Mitigation rules:**
1. Sanitize `filename`/`path` before interpolation.
2. Wrap attacker-influenced data in an explicit, clearly-delimited data block.
3. Never let filename/path content influence the `MachineState` directly.
4. Validation gate (§4) checks for refusal boilerplate.
