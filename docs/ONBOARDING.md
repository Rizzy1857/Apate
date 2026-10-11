# Mirage developer onboarding

Reviewed 2026-09-25. Begin with the [plan index](PLAN_INDEX.md), then read the [MVP](RESEARCH_MVP.md), [architecture](RESEARCH_ARCHITECTURE.md), and [backlog](IMPLEMENTATION_BACKLOG.md).

## Repository model

- `src/chronos/gateway`: Paramiko SSH endpoint, restricted worker and command emulator.
- `src/chronos/interface` and `core`: FUSE callbacks, session state, content mutation, durable audit outbox and PostgreSQL delivery.
- `src/chronos/intelligence`: optional local artifact generation, validation, fallback and provenance.
- `src/chronos/watcher`: audit consumption, derived evidence and exports.
- `src/chronos/dashboard`: native Rust research console.
- `src/chronos/simulation` and `layer0`: mostly deferred/experimental paths unless a current requirement names them.
- `tests`: default regressions plus opt-in Linux, live-model and disruptive infrastructure checks.

The working tree already contains user changes in dashboard, SSH and FUSE files. Preserve them. Use `apply_patch` for edits and never clean/reset unrelated work.

## Safe first checks

Install pinned Python dependencies in an isolated environment and ensure `redis-server` is available. From the repository root:

```bash
PYTHONPATH=src pytest -q --tb=short
cargo check --manifest-path src/chronos/dashboard/Cargo.toml
```

As of the documented 2026-09-28 review, Python returned 101 passed and 7 skipped with no warnings; see [status](STATUS.md). The default suite uses disposable Unix-socket Redis. Do not enable `--legacy-infrastructure` until you inspect the selected tests: they can mutate external services.

Before Docker work, inspect `docker-compose.yml`, any automatically loaded `docker-compose.override.yml`, and the [verification plan](VERIFICATION_PLAN.md). Set required secrets in the environment and avoid printing rendered configuration into shared logs. Linux FUSE integration is the supported container target; macOS uses a local relay/override and does not itself establish Linux release behavior.

## Change workflow

1. Select one W/B/R item and record the current source/patch identity.
2. Reproduce the behavior with the smallest meaningful test.
3. Change the authoritative state/evidence path first, then its projections and UI.
4. Run focused tests and appropriate broader regressions.
5. Update the completion record with actual results and limitations.
6. Do not mark a requirement verified from code presence or compilation alone.

Use precise language: attempted, admitted, emulated, completed, failed, denied, unsupported, interrupted, or unknown. Keep raw evidence separate from interpretations. Treat shell input, paths, generated content and imported evidence as untrusted.

## Current first package

The shell contract and B1–B12 fixes have verification evidence. Use [STATUS.md](STATUS.md) and the latest release evidence index for remaining gates; the backlog records the work and its limits. Future protocols, frontends and model providers require a separate scope decision.
