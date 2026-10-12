# Mirage developer onboarding

Reviewed 2026-10-12. The controlled-lab Research MVP is complete; begin with the [release evidence](RELEASE_EVIDENCE_INDEX_2026-10-11.md) and [current status](STATUS.md), then read the [MVP](RESEARCH_MVP.md), [architecture](RESEARCH_ARCHITECTURE.md), and [backlog](IMPLEMENTATION_BACKLOG.md).

## Repository model

- `src/chronos/gateway`: Paramiko SSH endpoint, restricted worker and command emulator.
- `src/chronos/interface` and `core`: FUSE callbacks, session state, content mutation, durable audit outbox and PostgreSQL delivery.
- `src/chronos/intelligence`: optional local artifact generation, validation, fallback and provenance.
- `src/chronos/watcher`: audit consumption, derived evidence and exports.
- `src/chronos/dashboard`: native Rust research console.
- `src/chronos/simulation` and `layer0`: mostly deferred/experimental paths unless a current requirement names them.
- `tests`: default regressions plus opt-in Linux, live-model and disruptive infrastructure checks.

The finalized implementation is committed as `fde3b98`. Check the current working tree before each change and preserve any subsequent user edits; never clean/reset unrelated work. The October 11 frozen bundle remains the immutable test reference even when living documentation changes.

## Safe first checks

Install pinned Python dependencies in an isolated environment and ensure `redis-server` is available. From the repository root:

```bash
PYTHONPATH=src pytest -q --tb=short
cargo check --manifest-path src/chronos/dashboard/Cargo.toml
```

The 2026-10-11 frozen-source suite returned 244 passed and 7 explicitly skipped; four locked Rust tests also passed. See [status](STATUS.md). The default suite uses disposable Unix-socket Redis. Do not enable `--legacy-infrastructure` until you inspect the selected tests: they can mutate external services.

Before Docker work, inspect `docker-compose.yml`, any automatically loaded `docker-compose.override.yml`, and the [verification plan](VERIFICATION_PLAN.md). Set required secrets in the environment and avoid printing rendered configuration into shared logs. Linux FUSE integration is the supported container target; macOS uses a local relay/override and does not itself establish Linux release behavior.

## Change workflow

1. Select one W/B/R item and record the current source/patch identity.
2. Reproduce the behavior with the smallest meaningful test.
3. Change the authoritative state/evidence path first, then its projections and UI.
4. Run focused tests and appropriate broader regressions.
5. Update the completion record with actual results and limitations.
6. Do not mark a requirement verified from code presence or compilation alone.

Use precise language: attempted, admitted, emulated, completed, failed, denied, unsupported, interrupted, or unknown. Keep raw evidence separate from interpretations. Treat shell input, paths, generated content and imported evidence as untrusted.

## Starting post-MVP work

The shell contract, B1–B12 corrections and G1–G7 gates have bounded verification evidence. There are no remaining mandatory gates for this frozen MVP. Start new work from [RESEARCH_FUTURE.md](RESEARCH_FUTURE.md); prioritize dependency reassessment and incremental evidence projection before broader deployment or concurrency. Future protocols, frontends, model providers and Home require a separate scope decision.
