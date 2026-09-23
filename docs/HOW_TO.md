# Mirage User Guide

> Repository codename: **Apate**
>
> Product name: **Mirage**
>
> Framework name: **Chronos**

This guide is for people who want to run Chronos, inspect it, or test it without first reading the entire architecture stack. It covers the practical path from startup to verification.

## Quick Start

### Start the system

```bash
docker-compose up -d
docker ps --filter "name=chronos"
docker logs chronos_core
```

### Enter the honeypot

```bash
docker exec -it chronos_core /bin/bash
cd /mnt/honeypot
ls -la
cat etc/passwd
```

Those file operations are intercepted by FUSE, recorded in Redis, analyzed for suspicious patterns, and written to PostgreSQL for later review. The system is trying to be useful, which is an admirable habit in infrastructure.

## Architecture Overview

Chronos is organized as a stack rather than a single monolith.

- The FUSE layer intercepts file operations.
- Redis stores live state and command history.
- The intelligence layer classifies commands and profiles behavior.
- PostgreSQL stores audit history and session records.
- Layer 0 in Rust handles fast protocol tagging before the Python side gets involved.

## Manual Testing

### Core system

```bash
make up
make validate-core
make validate-attacks
make verify
```

### Phase verification

```bash
python3 tests/verification/verify_phase1.py
python3 tests/verification/verify_phase2.py
python3 tests/verification/verify_phase3.py
python3 tests/verification/verify_phase4.py
```

### Demo mode

```bash
python3 tests/integration/demo_standalone.py
```

The demo simulates an attack session and shows command analysis, threat matching, skill profiling, phase detection, and risk scoring.

## Layer 0: The Rust Speed Layer

Layer 0 is a fast first pass for protocol classification and threat tagging.

- It classifies traffic before the higher layers do more work.
- It filters obvious noise.
- It escalates only the interesting cases.
- It is intentionally deterministic. Ambition is useful; surprise is less so.

## Troubleshooting

### Docker services are not starting

- Check `docker ps` for failed containers.
- Run `docker compose up --build` without `-d` to see startup logs.
- Confirm the required volumes and ports are available.

### FUSE mount is unavailable

- Make sure the container has `CAP_SYS_ADMIN` and `/dev/fuse` mapped.
- Confirm the container is running with the expected privileged settings.

### Generated content looks repetitive

- Verify the configured LLM provider.
- Check whether cached blob content is being reused as intended.
- Confirm the persona profile matches the file type you are reading.

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Developer Onboarding](ONBOARDING.md)
- [Roadmap](ROADMAP.md)
- [Current Status](STATUS.md)
- [Test Suite Guide](../tests/README.md)
