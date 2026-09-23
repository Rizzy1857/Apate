# Mirage Developer Onboarding

> Repository codename: **Apate**
>
> Product name: **Mirage**
>
> Framework name: **Chronos**

This guide is the short path into the project. It is written for two jobs: understanding the project quickly and running a clean demo without memorizing the whole codebase.

## What Mirage Is

Mirage is a state-consistent honeypot platform.

In plain terms:
- It looks like a real system to an attacker.
- It keeps filesystem state consistent.
- It logs activity for later analysis.
- It can generate file content when a file is missing or empty.
- It uses LLMs for content, not for state truth.

## What To Show In A Demo

If you need to explain the project to someone quickly, show these five things:

1. The fake system feels real.
   - Start the stack.
   - Open the container.
   - Show that the filesystem responds like a normal Linux environment.

2. State stays consistent.
   - Create or modify something.
   - Show that later reads still match the earlier change.
   - Point out that the system remembers because state is stored, not guessed.

3. Missing files can still look believable.
   - Read a file that does not yet have content.
   - Show that the persona engine generates content.
   - Read it again and show the same content comes back.

4. Attacks are observed, not ignored.
   - Run a few suspicious commands.
   - Show command analysis, threat tagging, or logs.
   - Explain that the system tracks behavior rather than just printing responses.

5. The project has a layered design.
   - FUSE handles the filesystem view.
   - Redis handles live state.
   - PostgreSQL stores audit history.
   - Rust handles early protocol analysis.

## Easiest Demo Flow

Use this order if you want the least friction:

### 1. Start the stack

```bash
make up
```

### 2. Confirm the services are running

```bash
docker ps --filter "name=chronos"
```

### 3. Open the honeypot container

```bash
docker exec -it chronos_core /bin/bash
cd /mnt/honeypot
```

### 4. Show the filesystem

```bash
ls -la
cat etc/passwd
```

### 5. Show a state change

```bash
touch /tmp/demo-file
ls /tmp
```

### 6. Show a generated file

```bash
cat /etc/anything-that-does-not-exist-yet
```

### 7. Show analysis or logs

Back on the host:

```bash
docker compose logs -f core-engine
```

## Simple Explanation Script

If someone asks what the project does, say this:

> Mirage is a honeypot that keeps state consistent. It behaves like a real filesystem, stores truth in Redis, keeps audit history in PostgreSQL, and uses AI only to fill in missing content. The point is to make attacker interaction believable without letting the system contradict itself.

## What To Say About The Architecture

Keep it short:

- FUSE gives the attacker a real filesystem interface.
- Redis and Lua keep state atomic.
- PostgreSQL keeps the audit trail.
- The persona engine generates content when needed.
- Rust handles fast protocol analysis.

That is enough for most demos. The project has more moving parts, but those are the parts that matter first.

## Useful Commands

```bash
make up
make validate-core
make validate-attacks
make verify
python3 tests/integration/demo_standalone.py
```

## Working Notes

- Keep the demo focused on state consistency and observability.
- Avoid diving into too many internal files unless asked.
- If the audience wants more detail, move from the demo flow to the architecture guide.
- If something fails during the demo, show the logs and keep going. A controlled failure is still a useful result.

## Where To Read Next

- [How To Use Chronos](HOW_TO.md)
- [Architecture](ARCHITECTURE.md)
- [Current Status](STATUS.md)
- [Roadmap](ROADMAP.md)
- [Test Suite Guide](../tests/README.md)
