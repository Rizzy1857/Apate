# ARM64 private staging gate verdict October 19

The three requested predeployment gates are complete for private authorized
testing on a dedicated disposable ARM64 Linux VM. Public attacker exposure is
not approved. Azure provisioning, registry publication and host-specific smoke
checks remain deployment steps, not completed cloud actions.

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Linux integration | Passed on native ARM64 Linux under Docker Desktop | `evidence/deployment_gates_20261019/linux-final-integration.log` |
| Authenticated hour | Passed all eight slots for at least 3,600 seconds | `evidence/authenticated_soak_20261019_final` |
| Image vulnerability review | Completed; infrastructure findings remediated, residual core risk accepted for private testing only | [Security review](DEPLOYMENT_SECURITY_REVIEW_2026-10-19.md) and `evidence/deployment_gates_20261019/operator-risk-acceptance.json` |

## Exact candidate and results

The soak ran from the immutable extracted source in
`evidence/release_candidate_20261019_final`. All 202 extracted hashes verified.
Source archive SHA-256 is
`e925f70b945432d9a889376eb55859ece3b7c2471500d198b23e48968b23b37a`;
manifest SHA-256 is
`11239bef4ae41ca535c667c655148ff0b52b137f2cb2ed5e9e14d4b0a9fd4483`.
It is based on `cf99f53` plus archived working-tree changes, not that commit alone.
All 71 deployed application/configuration file hashes matched the core image.

- Core: `sha256:ac671e6fe7797039c8f787edff3ba977293b6dd44c7dd921b1f5e475e38346d8`.
- Non-root Redis: `sha256:b5e97ff80e21bec8306ef3c9bf26c1d2fd6926b476c162a3641599aed20ac06c`.
- Non-root PostgreSQL: `sha256:2fcb9cef6f472fbf055a04dc6b8318dd4d47ddb5486ab9379bf8ed6436d33eee`.

These are local immutable image identities, not registry publication digests.
Scan reports' filesystem layer identities matched the inspected images. Final
image configuration and actual server-process checks confirm Redis UID 999 and
PostgreSQL UID 70. The core remains privileged for FUSE.

The hour reconciled all 7,042 submitted commands, successful results and projected
commands, and finalized 16 session summaries. All 16 paused run namespaces were
retained on one device with transient ownership removed. This is namespace and
ownership verification, not exhaustive file-byte verification. Client p95 was
150.0 ms, maximum 665.5 ms. Median core-memory growth was 52.45 MiB against the
predeclared 128 MiB bound, peak memory 474.1 MiB, and no OOM occurred. There were
595 samples with a maximum 6.123-second gap. Initial regression execution and
lightweight read-only inspections were co-resident; this is not an isolated
benchmark or a claim of indefinite capacity.

The frozen and final checkout Python suites each passed 272 tests with seven
explicit skips. Rust passed 13 with one opt-in integration test ignored. Linux
checks covered worker containment, real FUSE/SSH, session isolation, killed-worker
recovery, database-outage/uncertain-commit audit recovery and export reconciliation.
Skips are not passes. Deterministic generation remains the baseline; no model
training or universal attack coverage is claimed.

## Standalone staging configuration

The actual standalone Compose startup initially failed because an unquoted YAML
flow-list split the tmpfs options into separate mounts. Quoting the mount fixed
it, and a regression assertion now guards the exact option string. The corrected
configuration uses the same mount options exercised by the soak; no runtime
application or image changed after the hour.

`evidence/deployment_gates_20261019/standalone-smoke-retry/result.json` records the
passing real startup, FUSE/SSH filesystem probe, clamped root traversal,
Redis/PostgreSQL authentication, enabled persistent runs, loopback-only 2222 and
no database host ports. Both uniquely named smoke projects and their disposable
volumes were removed. The first failure remains retained, not relabeled passed.

The final handoff archive at `evidence/release_candidate_20261019_handoff` captures
the corrected configuration, reusable staging smoke procedure and reconciled
status documents. Its own manifest identifies those post-soak changes; deployed
application files and soak workload files must remain identical to the tested
candidate. This index is excluded from source archives to avoid self-reference.

The handoff contains 203 individually verified files. Archive SHA-256:
`3c489862a368a2f147b95fb0dc44a7d39bcf4206186bccdedc781822a8fc66c7`;
manifest SHA-256:
`05441c3ea707c0d953fd7c57dab919d338b04ee4c00b70c5542fa91de97c6d85`.
Comparison confirmed that application/configuration files inside the image and
the soak workload files are unchanged. Post-soak changes are status documents,
the corrected standalone Compose mount, its validation assertion, the new smoke
procedure and evidence ignore exceptions. Machine-readable closeout is in
`evidence/deployment_gates_20261019/verification.json`.

## Security disposition and next step

Offline scans with the October 19 vulnerability database found no known findings
in the final Redis/PostgreSQL filesystem images. Core retains 164 OS-package/
advisory pairs: 44 high, 58 medium, 61 low, one unknown and no critical; no Python
findings. All eight unique high advisories are reviewed without declaring them
patched or universally non-exploitable. The operator explicitly accepted only
private authorized testing on a disposable VM. See the linked security review
for exact scanner/database scope and containment limits.

Follow [Azure staging](AZURE_STAGING.md): publish and pin these reviewed images,
provision the isolated ARM64 VM, rerun host-dependent checks, establish backup/
restore, retention, disk monitoring and budget controls, and use private/tunneled
access. Do not attach production identities or data. The macOS GUI is not a
remote Azure management plane. Live evidence caching still rewrites growing
session summaries; the bounded soak does not establish production-scale I/O
efficiency. No Azure resource, commit, remote push or image publication was
performed in this verification turn.
