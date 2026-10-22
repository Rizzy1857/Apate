# Working and failure-path review — October 22, 2026

Scope: the current dirty checkout and the existing October 19 ARM64 core/hardened infrastructure images, in disposable local Docker stacks. No Azure resources were created; no registry publishing, public exposure, model downloads or production-data changes were performed. Application code was not changed by this review. Documentation corrections do not replace the frozen release archive.

## Results and evidence

| Check | Result | What it establishes |
|---|---|---|
| `PYTHONPATH=src pytest -q --tb=short -rs` | 272 passed, 7 skipped | Default behavioral/regression suite; skips are opt-in external-service mutation tests |
| `cargo test --locked --manifest-path src/chronos/dashboard/Cargo.toml` | 13 passed, 1 ignored | Native lifecycle/config/export unit contracts; actual managed export integration is separately opt-in |
| `tests/integration/run_linux.sh` with reviewed images | Passed | Real Linux worker confinement, FUSE SSH, denied features, forced worker termination, DB outage/uncertain-commit deduplication and export reconciliation |
| Standalone staging smoke | Passed; cleanup succeeded | Fake SSH filesystem/root clamp, required Redis/PostgreSQL authentication, persistent mode, configured loopback-only SSH and no DB host ports |
| Authenticated PostgreSQL outage under load | Passed | About 30-second pause; 1,205 submitted/audited/successful/projected commands, four sessions and retained paused namespaces |
| Authenticated Redis interruption | Passed | Four sessions closed; 82 confirmed commands retained among 86 audited submissions; four reconciled disconnects, paused runs retained |
| Authenticated core SIGKILL/restart | Passed | All 84 confirmed commands audited; four interrupted disconnects reconciled; paused runs retained and fresh-session isolation verified |

Python initially returned 224 passes, seven skips and 48 Redis fixture setup errors inside the sandbox. With permission to create the disposable Redis Unix socket it passed as above. Docker was initially stopped; it was started before container checks. These environmental failures are recorded, not counted as product passes. Python/Rust/Linux terminal results are in the task transcript; machine-readable container evidence is below.

- [Staging result](../evidence/working_review_20261022_staging/result.json)
- [PostgreSQL result](../evidence/working_review_20261022_postgres/result.json), [client reconciliation](../evidence/working_review_20261022_postgres/client.log), [image/source match](../evidence/working_review_20261022_postgres/image_source_match.json)
- [Redis result](../evidence/working_review_20261022_redis/result.json), [client reconciliation](../evidence/working_review_20261022_redis/client.log)
- [Core result](../evidence/working_review_20261022_core/result.json), [client reconciliation](../evidence/working_review_20261022_core/client.log)

Each load run records source hashes, image inventory, samples and logs in its evidence directory. The PostgreSQL preflight matched all 71 application files to the tested image. Core image ID: `sha256:ac671e6fe7797039c8f787edff3ba977293b6dd44c7dd921b1f5e475e38346d8`. Staging records exact Redis/PostgreSQL IDs too. Tags are local names, not published registry references. No fresh vulnerability scan was performed; the October 19 scan is dated evidence, not a guarantee of today's advisory state.

## Success/failure coverage map

| Area | Positive cases | Negative/boundary cases | Coverage source |
|---|---|---|---|
| Shell contract | Declared commands, identity, cwd, status, pipelines/redirection | Unsupported syntax/commands, invalid arguments, quote semantics, oversized ASCII/UTF-8 lines | `test_command_*`, `test_gateway_hardening.py`, Linux SSH |
| Filesystem | Reads, writes, copy/truncate, session namespaces | Traversal confinement, cross-session access, concurrent writes, storage bounds | `test_hardening.py`, Linux confinement/FUSE |
| Persistence/persona | Stable device facts, explicit resume, retained cwd/files | Fresh isolation, concurrent/active resume, profile mismatch, one-use selection | `test_persistent_persona.py`, `test_research_runs.py` |
| Audit | Durable delivery, correlated outcomes, replay | DB outage, uncertain commit, duplicate/conflicting events, full-spool admission rejection | Linux audit recovery, `test_research_report.py`, `test_hardening.py` |
| Generation | Deterministic output, current prepared bundle | Invalid mode, missing/mismatched bundle, oversized output, deadlines, stale generation fencing, fallback | `test_prepared_artifacts.py`, `test_inference_deadline.py`, `test_hardening.py` |
| Live state | Collection/generation state transitions | Stalled watcher/delivery and stale state | `test_operational_health.py`; not a fresh visual GUI walkthrough |
| Export | Raw/redacted snapshots, integrity hashes | Existing destination refusal, unknown mode, seeded secret omission, partial-transfer completion discipline | Python reporting and Rust managed-export tests; Linux DB export |
| Native lifecycle | Private credential reuse/migration, scoped Compose | Conflicting credentials, lock exclusion, bounded stall/cancellation, nonzero startup status | Rust tests; not all native platform interactions |
| Deployment | Actual standalone startup and fake-root check | Wrong/no database credentials, prohibited port exposure | Staging smoke; actual Azure ingress remains untested |

Tests exercise observable contracts and selected fault injections. They cannot prove “every possible failure” or universal attack resistance. Simulated full-spool/storage limits are not a real host-disk exhaustion drill.

## Documentation corrections

- Replaced obsolete “not release-ready” guidance with the specific private-testing scope and dated evidence.
- Put credentials before startup; distinguish new volumes from reuse of original passwords.
- Explain managed startup/shutdown, persistent-run resume/fresh semantics and the non-identity-bound resume limitation.
- Separate base development images from hardened staging image scan results.
- Correct in-container export PostgreSQL port to 5432 and explain ephemeral export paths, copying, privacy and pending audit events.
- Explain why model downloads cannot rely on the internal research network; provide isolated provisioning/cache attachment steps without enabling participant egress.
- Add failure symptoms, recovery boundaries, backup caveats and executable disposable test commands.

See [HOW_TO.md](HOW_TO.md) for usage, [tests/README.md](../tests/README.md) for reproduction and [AZURE_STAGING.md](AZURE_STAGING.md) for private deployment.

## Still outside this review

1. Actual ARM64 Azure VM kernel/FUSE, NSGs, administrator tunnel and host-port reachability; verify after provisioning, before admitting participants.
2. A fresh visual GUI walkthrough and platform-specific packaging/signing acceptance. Unit tests do not establish these.
3. Full backup/restore onto a separate deployment, real disk exhaustion, host power loss, indefinite retention and multi-day reliability.
4. Fresh live-model quality evaluation or training. Deterministic remains the supported default.
5. Fresh vulnerability scan and image rebuild/publish. Previously accepted core risks remain; public exposure requires a separate decision and mitigation.

The October 19 3,600-second authenticated eight-client soak remains historical capacity evidence (7,042 commands/16 sessions), not a new measurement here. Short failure runs are not substitutes for an hour or estimates of production capacity. Retained research state and growing evidence traffic require storage/retention planning.
