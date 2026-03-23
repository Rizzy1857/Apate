# 🎓 Mirage Developer Onboarding (Chronos Framework)

**Naming convention:** Repository codename is **Apate**. Product/idea name is **Mirage**. Framework implementation name is **Chronos**.

**Program phases:**
- **Phase 1 (6 months):** Core systems and validation (complete)
- **Phase 2 (6 months):** AI integration focused on improving analyst value while avoiding unnecessary complexity

Welcome to the **Chronos Framework**. This guide will help you build a mental model of how the system works so you can contribute effectively.

---

## 0. Five-Minute Explanation (Problem → Solution → Why It Matters) 🧠

If you need to explain Chronos in under five minutes to a technical panel, use this:

### The Core Problem

Most honeypots fail for one reason: **state inconsistency under adversarial interaction**.

Attackers do not just run one command. They run chains of dependent actions and test whether the environment has memory:

1. `touch /tmp/.x`
2. `ls /tmp`
3. `cat /tmp/.x`
4. `stat /tmp/.x`

If any step contradicts a prior step, the deception is exposed. Traditional script-based honeypots often return plausible text, but they do not maintain a coherent filesystem state graph over time. LLM-only systems improve linguistic realism, but still break when context windows expire or when state must be updated atomically across concurrent events.

In short: **the bottleneck is not language quality; the bottleneck is transactional truth.**

### The Chronos Solution

Chronos treats deception as a systems problem, not a prompt problem.

- **FUSE-backed interface**: all attacker interactions become real filesystem syscalls.
- **State Hypervisor (Redis + Lua)**: mutations are handled atomically, persisted, and auditable.
- **Persona Engine (LLM)**: generates missing content lazily, then commits it to durable state.
- **Audit-first design**: relevant interactions are captured for threat analysis.

The key design move is simple: *generate once, persist, and reuse consistently*. This supports high apparent depth while maintaining internal coherence.

### Why This Is Convincing

Chronos closes the realism gap at the exact layer attackers validate: operational consistency.

- It survives sequential command chaining because state is durable.
- It survives concurrency because writes are atomic.
- It scales realism because LLM output is state-committed, not ephemeral.
- It supports forensics because interactions are logged as structured events.

This means Chronos is not merely a fake shell; it is a **state-consistent adversarial interaction environment**.

### 30-Second Version (for slides)

> Existing honeypots fail when attackers test continuity. Chronos solves continuity at the syscall layer using FUSE + Redis atomic state, then uses LLMs only to fill missing content that is immediately persisted. Result: realistic interaction that remains logically consistent over time, with auditability built in.

---

## 1. The Big Picture 🌍

**Chronos is a state-consistent deception engine.**

Unlike traditional honeypots that *pretend* to be a server using static scripts, Chronos *is* a filesystem that generates itself on the fly.

*   **The Problem**: In old honeypots, if an attacker ran `touch /tmp/a` and then `ls /tmp`, the file wouldn't be there because the "commands" were just fake text responses.
*   **The Solution**: Chronos implements a REAL filesystem (FUSE). When an attacker runs `touch`, we actually create an entry in our database. When they run `ls`, we read from that database. It behaves exactly like Linux because it respects system calls.

---

## 2. The Architecture (Simplified) 🏛️

Think of Chronos as a standard web app, but instead of "Users" and "Posts", we store "Inodes" and "Files".

1.  **The Interface (Skin)**: `src/chronos/interface/fuse.py`
    *   This python script pretends to be a hard drive.
    *   Linux sends it requests: "Read bytes 0-100 of File X".
    *   It translates those requests into Database lookups.

2.  **The Brain (Hypervisor)**: `src/chronos/core/state.py`
    *   The logic layer.
    *   "Create a file? Okay, let me check if that name is taken, allocate an ID, and save it."

3.  **The Memory (Redis)**: `docker-compose.yml` -> `redis-store`
    *   The actual database.
    *   We don't store files on disk! We store them as keys in Redis.
    *   If you restart the container, Redis keeps the data (Persistence).

4.  **The Imagination (Persona Engine)**: `src/chronos/intelligence/`
    *   If a file *doesn't* exist (e.g., attacker checks `/etc/secret_password`), we don't say "404 Not Found".
    *   We ask an LLM: "What would be inside `/etc/secret_password`?"
    *   We save that result. Now the file exists forever.

---

## 3. Directory Map 🗺️

```text
src/chronos/
├── core/               # The "Backend" Logic
│   ├── state.py        # State Hypervisor (The boss)
│   ├── database.py     # Redis wrapper
│   └── lua/            # Atomic scripts (prevent race conditions)
├── interface/          # The "Frontend" (FUSE)
│   └── fuse.py         # Handles syscalls (read/write/mkdir)
├── intelligence/       # The "AI"
│   ├── persona.py      # Manages system personalities
│   └── llm.py          # Connects to OpenAI/Anthropic
└── layer0/             # The "Reflexes"
    └── rust-protocol/  # High-speed packet analysis (Rust)
```

---

## 4. Life of a Command 🔄

### Scenario A: Attacker writes a file
**Command**: `echo "hacked" > /tmp/pwn`

1.  **OS** calls `create("/tmp/pwn")`.
2.  **FUSE** tells **State Hypervisor**: "Create this file".
3.  **Hypervisor** runs a **Lua Script** in Redis:
    *   Checks if `/tmp` exists.
    *   Allocates new Inode ID (e.g., `105`).
    *   Links `pwn` -> Inode `105`.
4.  **OS** calls `write(inode=105, data="hacked")`.
5.  **FUSE** saves "hacked" into Redis blob storage.

### Scenario B: Attacker reads a "Ghost" file
**Command**: `cat /var/log/nginx/access.log` (Does not exist yet)

1.  **OS** calls `read("/var/log/nginx/access.log")`.
2.  **FUSE** sees the file has **No Content Hash**.
3.  **FUSE** calls **Persona Engine**.
4.  **Persona Engine** asks LLM: *"Generate nginx access logs for a Ubuntu server"*.
5.  **LLM** returns text.
6.  **FUSE** saves text to Redis.
7.  **FUSE** returns text to Attacker.
    *   *Next time they read it, it comes directly from Redis (Fast!).*

---

## 5. Developer Cheatsheet ⌨️

**Start everything:**
```bash
make prod
```

**Check logs (is the AI generating?):**
```bash
make logs
```

**Enter the matrix (Manual Test):**
```bash
make shell
cd /mnt/honeypot
```

**Reset the world (Wipe DB):**
```bash
make clean
```

---

## 6. Pro Tips 💡

*   **Logic in Lua**: If you need to change how files are created, edit `src/chronos/core/lua/atomic_create.lua`. We use Lua so operations are atomic (thread-safe).
*   **Debug Mode**: If `make prod` fails, try `docker compose up --build` (without `-d`) to see startup errors immediately.
*   **LLM Config**: To use real AI, set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...` in `docker-compose.prod.yml`.
