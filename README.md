# Mirage (Chronos Framework)

> October 19: the ARM64 candidate passed Linux integration, the authenticated
> one-hour soak and standalone staging startup. The vulnerability review is
> complete with residual core risks accepted for **private testing only**.
> See the [current gate verdict](docs/RELEASE_EVIDENCE_INDEX_2026-10-19.md) and
> [Azure staging guide](docs/AZURE_STAGING.md). Public attacker exposure is not approved.

> The integrated Research implementation includes persistent persona,
> live operations and GUI-managed services. See the [current acceptance verdict](docs/RELEASE_EVIDENCE_INDEX_2026-10-19.md)
> and [implementation progress](docs/INTEGRATED_PRODUCT_PROGRESS.md).
> The completed Research MVP verdict below applies to the October 11 frozen
> archive, not to the newer working-tree changes.

> Repository codename: **Apate**
>
> Product name: **Mirage**
>
> Framework name: **Chronos**

Mirage is a research SSH deception project built on the Chronos framework. It emulates a limited command environment with isolated filesystem state and records interactions for analysis. The **Research MVP is complete for controlled local lab use**, with G1–G7 passed under the documented procedures. Mirage Home remains a separate future product.

Status reviewed 2026-10-22. Use the [current working review](docs/WORKING_REVIEW_2026-10-22.md) and [October 19 release evidence](docs/RELEASE_EVIDENCE_INDEX_2026-10-19.md) for tested scope and limitations. The candidate includes working-tree changes: a commit ID alone does not identify it. This review does not assert remote publication or replace historical frozen archives.

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
`.local-deploy/`; later launches reuse them. Older credential files are upgraded with a private Redis password while preserving database credentials. Quit the GUI before rebuilding it.
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

The October 19 candidate passed its documented private-testing gates. See the
[desktop verification](docs/DESKTOP_VERIFICATION_2026-10-15.md) and
[implementation progress](docs/INTEGRATED_PRODUCT_PROGRESS.md). Manual Compose
startup below remains available; managed services use dedicated names and ports.

### Prerequisites

- Docker and Docker Compose with a supported Linux FUSE runtime
- Required database credentials; current Compose also requires `REDIS_PASSWORD` and `GRAFANA_PASSWORD` during configuration interpolation
- Deterministic startup requires no model service. Local Ollama is optional for prepared-artifact experiments or bounded lazy-generation tests.

### Run the stack

```bash
git clone https://github.com/Rizzy1857/Apate.git chronos
cd chronos
# For a NEW disposable deployment; retain these secrets securely.
# Existing volumes require their original credentials instead.
export REDIS_PASSWORD="$(openssl rand -hex 32)"
export POSTGRES_PASSWORD="$(openssl rand -hex 32)"
export GRAFANA_PASSWORD="$(openssl rand -hex 32)"
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml up --build -d
```

The [step-by-step operator guide](docs/HOW_TO.md) covers desktop/manual startup, SSH, persistence, live evidence, exports, optional models, shutdown and troubleshooting. Base Compose is a development graph using older infrastructure images; use the separate [staging guide](docs/AZURE_STAGING.md) for the reviewed ARM64 image set. Never paste rendered credentials into reports.

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

The October 22 rerun passed 272 Python tests (7 explicit infrastructure skips) and 13 Rust tests (1 integration test ignored). See the [working review](docs/WORKING_REVIEW_2026-10-22.md) for fresh container and failure-injection results. The October 19 authenticated one-hour soak reconciled 7,042 commands across 16 sessions at eight client slots; p95 was about 150 ms. That historical run is not a new October 22 capacity measurement.

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
- [Step-by-step operator guide](docs/HOW_TO.md)
- [Current success/failure coverage](docs/WORKING_REVIEW_2026-10-22.md)
- [Test Suite Guide](tests/README.md)

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Description | Default |
|---|---|---|
| `REDIS_PASSWORD` | Required Redis authentication password in Compose | unset |
| `REDIS_HOST` | Redis service host | `redis-store` |
| `POSTGRES_HOST` | PostgreSQL service host | `db-store` |
| `POSTGRES_PASSWORD` | Required Compose database password | unset |
| `OLLAMA_HOST` | Local inference endpoint host in Compose | `ollama` |
| `GRAFANA_PASSWORD` | Required by current Compose interpolation; monitoring service is optional | unset |

## License

MIT License.
