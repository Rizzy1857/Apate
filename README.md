# Mirage (Chronos Framework)

> Repository codename: **Apate**
>
> Product name: **Mirage**
>
> Framework name: **Chronos**

Mirage is a research SSH deception project built on the Chronos framework. It emulates a limited command environment with isolated filesystem state and records interactions for analysis. The bounded Research MVP is implemented; Mirage Home is a separate future product. Use the [release evidence index](docs/RELEASE_EVIDENCE_INDEX_2026-10-11.md) for the verified source bundle, gate decisions and limitations. The tested working tree includes changes beyond the base Git commit; cloning that commit alone does not reproduce this release.

Chronos combines a FUSE-backed filesystem, session-scoped Redis state, a durable SQLite audit outbox, PostgreSQL evidence storage, and optional LLM-assisted artifact generation. Selected filesystem mutations use Redis/Lua transactions. The model supplies bounded content for approved artifacts; deterministic code owns state.

## Product plan and status

- Start with the [authoritative documentation set](docs/PLAN_INDEX.md).
- [Research MVP](docs/RESEARCH_MVP.md), [implementation backlog](docs/IMPLEMENTATION_BACKLOG.md), and [verification gates](docs/VERIFICATION_PLAN.md) define completion.
- [Mirage Home](docs/MIRAGE_HOME.md) describes the future household sensor and optional research sharing.
- [Current status](docs/STATUS.md) distinguishes observed results from pending validation.

## What It Does

- Presents an Ubuntu-like, deliberately limited filesystem through FUSE.
- Stores session filesystem state in Redis and uses Lua for selected atomic mutations.
- Records audit and session data in PostgreSQL.
- Applies evidence-linked command-pattern rules. These labels do not estimate attacker expertise or identity.
- Generates content only for approved manifest artifacts and caches accepted or fallback content.
- Exposes an SSH emulator; HTTP and Rust Layer 0 are not established in the current core startup path.
- Provides a native Rust research console and snapshot export, with known gaps tracked in the backlog.

See the [current architecture and evidence contract](docs/RESEARCH_ARCHITECTURE.md).

## Quick Start

### Prerequisites

- Docker and Docker Compose with a supported Linux FUSE runtime
- Required database credentials; current Compose also requires `GRAFANA_PASSWORD` during configuration interpolation
- Deterministic startup requires no model service. Local Ollama is optional for prepared-artifact experiments or bounded lazy-generation tests.

### Run the stack

```bash
git clone https://github.com/Rizzy1857/Apate.git chronos
cd chronos
docker compose up --build -d
```

Set `POSTGRES_PASSWORD` and `GRAFANA_PASSWORD` securely in the environment before running. Inspect `docker compose config --quiet` and any local override first; do not paste rendered credentials into reports. Model provisioning and native UI setup must be validated for the chosen environment. This is not yet a verified one-command installation.

The default artifact treatment is deterministic. A stored AI-prepared bundle is loaded only when `CHRONOS_ARTIFACT_TREATMENT=prepared` is explicitly selected; a missing or incomplete current bundle stops initialization.

Check the core service logs:

```bash
docker compose logs -f core-engine
```

Interact through the SSH gateway:

```bash
ssh -p 2222 ubuntu@127.0.0.1
```

Filesystem access is attributed through registered worker PIDs; arbitrary container-shell access is not the supported session path. Inspect the expected host key rather than disabling host-key checking by default. Current authentication is permissive and the shell uses the configured profile user; this is a documented implementation limitation.

## Verification

Start with non-disruptive regression/build checks:

```bash
PYTHONPATH=src pytest -q --tb=short
cargo check --manifest-path src/chronos/dashboard/Cargo.toml
```

The Python suite requires dependencies and a runnable `redis-server`. See the [verification plan](docs/VERIFICATION_PLAN.md) before integration/recovery testing. Older Make targets and phase scripts are not a complete release gate and may access external infrastructure.

## Documentation

- [Plan index and decisions](docs/PLAN_INDEX.md)
- [Architecture and evidence contract](docs/RESEARCH_ARCHITECTURE.md)
- [Future research roadmap](docs/RESEARCH_FUTURE.md)
- [Current Status](docs/STATUS.md)
- [Test Suite Guide](tests/README.md)

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Description | Default |
|---|---|---|
| `REDIS_HOST` | Redis service host | `redis-store` |
| `POSTGRES_HOST` | PostgreSQL service host | `db-store` |
| `POSTGRES_PASSWORD` | Required Compose database password | unset |
| `OLLAMA_HOST` | Local inference endpoint host in Compose | `ollama` |
| `GRAFANA_PASSWORD` | Required by current Compose interpolation; monitoring service is optional | unset |

## License

MIT License.
