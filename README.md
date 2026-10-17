# Mirage (Chronos Framework)

> The integrated Research implementation includes persistent persona,
> live operations and GUI-managed services. See the [current acceptance verdict](docs/RELEASE_EVIDENCE_INDEX_2026-10-16.md)
> and [implementation progress](docs/INTEGRATED_PRODUCT_PROGRESS.md).
> The completed Research MVP verdict below applies to the October 11 frozen
> archive, not to the newer working-tree changes.

> Repository codename: **Apate**
>
> Product name: **Mirage**
>
> Framework name: **Chronos**

Mirage is a research SSH deception project built on the Chronos framework. It emulates a limited command environment with isolated filesystem state and records interactions for analysis. The **Research MVP is complete for controlled local lab use**, with G1–G7 passed under the documented procedures. Mirage Home remains a separate future product.

Status reviewed 2026-10-12. The implementation and release evidence are committed locally as `fde3b98` (`Finalize Mirage Research MVP and verified release evidence`). The last push attempt failed authentication; remote publication is not confirmed. Use the [release evidence index](docs/RELEASE_EVIDENCE_INDEX_2026-10-11.md) for the exact frozen source, results and limitations. This documentation refresh does not replace or alter that frozen archive.

Chronos combines a FUSE-backed filesystem, session-scoped Redis state, a durable SQLite audit outbox, PostgreSQL evidence storage, and optional LLM-assisted artifact generation. Selected filesystem mutations use Redis/Lua transactions. The model supplies bounded content for approved artifacts; deterministic code owns state.

## Product plan and status

- Start with the [authoritative documentation set](docs/PLAN_INDEX.md).
- [Research MVP](docs/RESEARCH_MVP.md), [implementation backlog](docs/IMPLEMENTATION_BACKLOG.md), and [verification gates](docs/VERIFICATION_PLAN.md) define completion.
- [Mirage Home](docs/MIRAGE_HOME.md) describes the future household sensor and optional research sharing.
- [Current status](docs/STATUS.md) separates completed MVP verification from residual risks and future work.

## What It Does

- Presents an Ubuntu-like, deliberately limited filesystem through FUSE.
- Stores session filesystem state in Redis and uses Lua for selected atomic mutations.
- Records audit and session data in PostgreSQL.
- Applies evidence-linked command-pattern rules. These labels do not estimate attacker expertise or identity.
- Generates content only for approved manifest artifacts and caches accepted or fallback content.
- Exposes an SSH emulator; HTTP and Rust Layer 0 are not established in the current core startup path.
- Provides a native Rust research console, paginated history, and private/raw or separately redacted snapshot exports.

See the [current architecture and evidence contract](docs/RESEARCH_ARCHITECTURE.md).

## Quick Start

### Managed desktop application (macOS development build)

With Docker Desktop running and Rust installed:

```bash
bash tests/integration/package_dashboard_macos.sh
open .local-deploy/Mirage.app
```

The GUI starts its local core, database, Redis and loopback relay, checks readiness,
and connects Live Ops. First launch saves private local credentials under
`.local-deploy/`; later launches reuse them. Quit the GUI before rebuilding it.
Normal shutdown removes managed service containers and keeps their data volumes.

Connect with `ssh -p 2222 ubuntu@127.0.0.1`. Under Live Ops, **Persistent runs**
lets the operator select a paused run for the next SSH shell, or start fresh.
Resume retains that run's files, device facts and directory. Fresh creates an
independent filesystem while retaining previous runs. The one-use resume
selection expires after 60 seconds; wait until a run is paused before resuming.
Only arm resume when you control the next connection: the selection is not bound
to a verified person or source, and this lab's permissive authentication does not
establish participant identity. Another concurrent connection can consume it.
Persona identity persists across application restarts. Shell environment variables
remain connection-local. Default generation is deterministic; no model fine-tuning
is implied by persistent persona grounding.

These integrated changes are still undergoing release validation. See the
[desktop verification](docs/DESKTOP_VERIFICATION_2026-10-15.md) and
[implementation progress](docs/INTEGRATED_PRODUCT_PROGRESS.md). Manual Compose
startup below remains available; managed services use dedicated names and ports.

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

The 2026-10-11 release passed 244 Python tests (7 explicit skips), 4 Rust tests, Linux/FUSE integration, and extracted-source fresh-build checks. A full one-hour soak at eight client slots reconciled 7,055 commands across 16 sessions; client p95 was 139 ms and median core-memory growth was 41.95 MiB. See the [capacity assessment](docs/G6_CAPACITY_ASSESSMENT_2026-10-11.md) for the exact workload and limits.

This is not public-production approval: the image scan retains known Debian vulnerabilities, longer-duration reliability is unmeasured, and the workload generated substantial internal evidence traffic. No universal attack coverage, attacker identity/expertise inference or AI-superiority claim is made. See the [release risk assessment](docs/G7_RELEASE_ASSESSMENT_2026-10-11.md).

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
