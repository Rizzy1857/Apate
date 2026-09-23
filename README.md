# Mirage (Chronos Framework)

> Repository codename: **Apate**
>
> Product name: **Mirage**
>
> Framework name: **Chronos**

Mirage is a state-consistent honeypot platform built on the Chronos framework. The goal is simple enough to state and demanding enough to deserve the work: preserve believable attacker interaction without letting the environment contradict itself.

Chronos combines a FUSE-backed filesystem, Redis-based atomic state, PostgreSQL audit storage, and optional LLM-assisted content generation. The LLM is used for texture, not truth. State remains deterministic; the interesting part is that it stays interesting.

## Program Phases

- Phase 1: Core deception platform engineering and validation, completed.
- Phase 2: AI integration that improves realism and analysis without adding unnecessary complexity, in progress.

## What It Does

- Presents a realistic filesystem through a FUSE interface.
- Persists filesystem state atomically in Redis.
- Records audit and session data in PostgreSQL.
- Classifies commands, threats, and attacker behavior.
- Generates missing file content on demand, then persists it for consistent reuse.
- Exposes SSH and HTTP entry points for attacker interaction.
- Uses a Rust layer for high-speed protocol analysis and early threat tagging.

For the technical case behind the design, see [Problem Validation Analysis](PROBLEM_VALIDATION_ANALYSIS.md).

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Optional: an OpenAI or Anthropic API key for content generation features

### Run the stack

```bash
git clone https://github.com/Rizzy1857/Apate.git chronos
cd chronos
docker compose up --build -d
```

Check the core service logs:

```bash
docker compose logs -f core-engine
```

Open the container and explore the mounted filesystem:

```bash
docker exec -it chronos_core /bin/bash
cd /mnt/honeypot
ls -la
```

## Verification

Run the core validation and verification targets from the repository root:

```bash
make up
make validate-core
make validate-attacks
make verify
```

You can also run the phase scripts directly:

```bash
python3 tests/verification/verify_phase1.py
python3 tests/verification/verify_phase2.py
python3 tests/verification/verify_phase3.py
python3 tests/verification/verify_phase4.py
```

For a lighter demonstration, use the standalone demo:

```bash
python3 tests/integration/demo_standalone.py
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Developer Onboarding](docs/ONBOARDING.md)
- [How To Use Chronos](docs/HOW_TO.md)
- [Roadmap](docs/ROADMAP.md)
- [Current Status](docs/STATUS.md)
- [Test Suite Guide](tests/README.md)

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Description | Default |
|---|---|---|
| `REDIS_HOST` | Redis service host | `redis-store` |
| `POSTGRES_HOST` | PostgreSQL service host | `db-store` |
| `LLM_PROVIDER` | `openai`, `anthropic`, or `mock` | `mock` |
| `OPENAI_API_KEY` | OpenAI API key, if used | unset |

## License

MIT License.
