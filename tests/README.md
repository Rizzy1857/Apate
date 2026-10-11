# Chronos test suite

Current release procedure: [docs/VERIFICATION_PLAN.md](../docs/VERIFICATION_PLAN.md). Test presence is not proof of a release gate.

## Default regression

From the repository root, with pinned dependencies and `redis-server` available:

```bash
PYTHONPATH=src pytest -q --tb=short
cargo check --manifest-path src/chronos/dashboard/Cargo.toml
```

The Python fixtures launch disposable Redis over a Unix socket. Tests named `test_concurrency.py` and `test_crash_recovery.py` are skipped unless `--legacy-infrastructure` is supplied because they can mutate external services. Inspect them and their target configuration before opting in.

Current directories:

- `tests/validation`: default behavioral, hardening, recovery, world-state and reporting regressions plus opt-in legacy tests.
- `tests/verification`: older phase-oriented scripts and manifest/evidence checks. They remain useful but are not the current phase governance model.
- `tests/integration`: demos, opt-in local-model checks, and Linux/Docker/FUSE recovery/load paths.

`tests/integration/run_linux.sh` builds a uniquely tagged test image and creates uniquely named disposable Redis/PostgreSQL/core containers and an internal network. Review it before execution. It requires Docker with Linux FUSE/capability support and does not cover all G1–G7. The script removes its containers, network and test image on exit.

Live-model tests require explicit environment opt-ins and an installed model. Record model digest, cache state, hardware and all rejected/fallback trials. Demos illustrate flows; they do not establish attack realism, detection quality or comparison with Cowrie.

For the optional valid-only prepared-artifact engineering comparison, use fresh output directories:

```bash
PYTHONPATH=src python3 tests/integration/evaluate_prepared_ai.py \
  --output evidence/prepared_ai_valid_RUN_ID --trials 30 \
  --reference-epoch 1790467200
PYTHONPATH=src python3 tests/integration/evaluate_deterministic.py \
  --output evidence/deterministic_valid_RUN_ID --trials 30 \
  --reference-epoch 1790467200
```

The AI harness checkpoints each trial, retains rejected attempts and records immutable model digests. Neither harness overwrites an existing run.

On 2026-10-11, the default suite passed 244 tests with 7 explicit infrastructure skips; the locked native dashboard suite passed 4 tests. See [STATUS.md](../docs/STATUS.md) for release scope and the evidence index for the frozen candidate.

For a deterministic one-hour capacity run, build the candidate image first and use a new evidence directory:

```bash
APATE_LOAD_IMAGE=apate-release:20261011 APATE_LOAD_SECONDS=3600 \
  APATE_LOAD_CLIENTS=8 APATE_LOAD_MAX_COMMANDS=0 APATE_LOAD_INTERVAL=4 \
  APATE_LOAD_OUTPUT=evidence/soak_NEW_RUN \
  python3 tests/integration/run_load.py
```

Keep the host awake (on macOS, prefix the Python command with `caffeinate -i`). Eight client slots rotate connections after 800 commands or 3,300 seconds, before the server's 1,000-command/one-hour limits. Rotation is recorded, and unexpected disconnects still fail. The verdict reconciles elapsed duration, submissions, distinct successful results, projected command counts, final summaries and namespace cleanup. The output directory retains source hashes, image identity, raw samples, client/core logs and the result. An interrupted process without a passing result is not a completed run. A supplied image is retained; automatically built test images and disposable containers/networks are removed.

Add tests around externally observable contracts and failure boundaries. Avoid tests that merely duplicate implementation. Keep disruptive tests on explicitly disposable targets.
