# Persistent-run capacity and recovery checkpoint — October 16, 2026

This is a bounded integration checkpoint, not the final extended-soak decision.
The historical October 11 one-hour test did not enable persistent runs and is
not reused as evidence that this mode passed a one-hour test.

## Runtime and procedure

Image: `mirage-desktop-candidate:20261016-v2-fresh`, manifest-list identity
`sha256:ef06e47e54a387266a11401aac9fe92caf98bd0809c9a70b01aea16205107de4`.
Application source matches the frozen v2 candidate. Load-harness-only changes
enable `APATE_LOAD_PERSISTENT_RUNS=1` and forward it to the core and clients.
Each run records actual image identity, parameters and source/harness hashes.
Those harness changes postdate the frozen archive; they do not change the
candidate application's implementation.

Resources are uniquely named disposable containers on internal networks. Core
limits are 2 CPUs, 2 GiB and 192 PIDs; Redis is 256 MiB with no eviction.
The active operator GUI remains untouched and shares the Docker VM, so results
are co-resident engineering observations, not uncontended benchmarks. Fault
fixtures run concurrently with each other after the control workload finishes.

The harness now waits for transient PID, session filesystem, run-ownership and
context keys to disappear. Persistent mode additionally requires every expected
run to be paused, its filesystem namespace retained, run/persona device IDs
consistent, and exactly one device for the unchanged profile. A regression test
rejects active runs, leaked ownership and missing retained filesystems. Default
Python regressions: 263 passed, 7 explicit skips.

## Three-minute control — passed

Eight client slots, no total-command early stop, one-second interval and
connection rotation every 60 seconds. Each command writes and reads an exact
synthetic token and reads the configured hostname. Measured client durations
were 180.000–180.003 seconds, with three sessions per slot.

1,308 commands = 1,308 audited submissions = 1,308 distinct successful results
= 1,308 projected commands. All 24 summaries finalized; all 24 runs paused and
retained their filesystem namespaces on one device. No transient ownership or
PID mappings remained. File-content survival across crash/resume is separately
covered by the native October 15 procedure; this load retention assertion checks
namespace existence, not byte-by-byte validation of every retained artifact.

Client latency: p50 75.4 ms, p95 190.8 ms, maximum 903.3 ms. Across 35 resource
samples, initial/final 12-sample memory medians were about 426.7/428.1 MiB,
growth about 1.4 MiB; peak 429.4 MiB. Median PIDs remained 58, peak 66 during
rotations. Core was running and not OOM-killed before teardown. Samples include
warm-up and post-client cleanup, not solely steady-state load.

Evidence: [run](../evidence/persistent_load_20261016/run.json),
[client result](../evidence/persistent_load_20261016/client.log),
[resource verdict](../evidence/persistent_load_20261016/result.json),
[samples](../evidence/persistent_load_20261016/samples.jsonl).

## Recovery checks

| Fault | Confirmed result |
|---|---|
| Core forcibly killed and restarted | Passed: all 118 client-confirmed commands were retained among 122 admitted attempts; all eight interrupted sessions received orphaned-session disconnects. Eight paused runs retained their namespaces on one device; transient ownership disappeared and a new session did not inherit old content. The additional four admitted attempts are not claimed client-confirmed. |
| PostgreSQL paused for 30.19 seconds | Passed: 1,735 submissions, distinct successful results and projected commands matched exactly. Eight summaries finalized; eight paused runs retained their namespaces on one device, without transient ownership. Client p95 209.7 ms, max 446.8 ms; these are co-resident fault-test observations. |
| Redis stopped and restarted | Retry passed: all 129 client-confirmed commands were retained among 137 admitted attempts; all eight interrupted sessions received orphaned-session disconnects. Eight paused runs retained their namespaces on one device; transient ownership disappeared and a new session did not inherit old content. The additional eight admitted attempts are not claimed client-confirmed. First attempt remains incomplete after turn interruption and Docker shutdown, not retroactively relabeled passed. |

Core evidence: [client](../evidence/persistent_core_recovery_20261016/client.log),
[result](../evidence/persistent_core_recovery_20261016/result.json).
PostgreSQL evidence:
[client](../evidence/persistent_postgres_recovery_20261016/client.log),
[result](../evidence/persistent_postgres_recovery_20261016/result.json).
Interrupted Redis attempt:
[record](../evidence/persistent_redis_recovery_20261016/interruption.json).
Redis retry: [client](../evidence/persistent_redis_recovery_20261016_retry/client.log),
[result](../evidence/persistent_redis_recovery_20261016_retry/result.json).
The retry ran after Docker Desktop was restarted; do not assume an identical
co-resident workload to the earlier concurrent fault fixtures.

Fault-run resource summaries include startup, outage and cleanup. Short runs
also have overlapping first/last memory windows; do not use their growth values
as independent steady-state memory-stability evidence. A process restarting or
accepting SSH alone is not a pass.

## Extended soak — failed after host lid closure

Started October 16 at 04:58:52 UTC. Eight client slots, 3,600 measured seconds,
no total-command early-stop cap, four-second interval and rotation after 3,300
seconds or 800 commands. `caffeinate -i` prevents idle sleep only for this test.
Run identity and samples are in `evidence/persistent_soak_20261016`.
The run failed after all eight clients completed 187 commands each and then lost
their connections. No full-duration reconciliation or capacity pass is claimed.

Host power logs confirm Clamshell Sleep at 10:41:32 IST for 145 seconds, followed
by DarkWake at 10:43:57 IST. Resource samples have a matching 149.091-second gap;
core logs report Session attribution expired for all eight workers. Suspension
outlasted the 120-second attribution lease, and sessions failed closed.
`caffeinate -i` prevents idle sleep, not forced lid-closure sleep. Do not restore
expired ownership or increase the lease solely to turn this test into a pass.
The original [failure](../evidence/persistent_soak_20261016/result.json),
[client log](../evidence/persistent_soak_20261016/client.log) and
[diagnosis](../evidence/persistent_soak_20261016/diagnosis.json) are retained.

Application and configuration files remain byte-identical to the tested image.
During the soak, build-context exclusions were added for `.local-deploy` and
`outputs`; those packaging-only changes prevent credentials/operator files from
entering future Docker build contexts. A static exclusion regression was added.
The full Python suite passed 264 tests with seven explicit skips. That host-side
test execution occurred early in the soak and is disclosed as co-resident work.

All three named short fault procedures passed. Still required: a fresh completed
one-hour soak with the lid open, host awake and Docker continuously running,
plus final acceptance reconciliation. The requirements audit is recorded
in INTEGRATED_ACCEPTANCE_AUDIT_2026-10-16.md.
This three-minute workload does not establish multi-hour or public operation,
32-client capacity, AI-generation throughput, long-term storage growth or
resilience to simultaneous loss of all stores.

## October 17 retry — passed for the frozen October 16 image

A fresh run started at 05:11:30 UTC (10:41:30 IST), using the same verified
image and workload: eight slots, 3,600 seconds, four-second interval, no early
command cap, persistent runs enabled and planned rotation. Resources are newly
named and disposable; the previous failure is unchanged. Idle sleep is prevented
while the harness runs, but the lid must remain open and Docker must stay running.
Evidence: [run identity](../evidence/persistent_soak_20261017_retry/run.json)
and [ongoing samples](../evidence/persistent_soak_20261017_retry/samples.jsonl).
The retry passed: every slot completed at least 3,600 measured seconds.
7,061 submissions, distinct successful results and projected commands matched
exactly. All 16 summaries finalized; 16 paused runs retained their namespaces
on one device and transient ownership disappeared. Client p95 was 141.0 ms,
maximum 246.1 ms. Memory median growth was 42.3 MiB (128 MiB allowance), peak
477.1 MiB; 601 samples had a maximum 6.191-second gap. Core was not OOM-killed.
See [client result](../evidence/persistent_soak_20261017_retry/client.log) and
[resource verdict](../evidence/persistent_soak_20261017_retry/result.json).

This result belongs to image `ef06e47e...`, not the current hardened checkout.
Eight source files already differed at run start: authenticated Redis clients,
managed credential migration and SSH/shell hardening. Tests were unchanged
during that run. No long-duration result is silently transferred to a new image.

## Reconciled authenticated candidate — short load passed

The current application was rebuilt as `mirage-reconciled:20261017`, identity
`sha256:cd3a4527e26caed741016cc86b5f2fc356b275e678280a050bb5f889839740b0`.
The harness now verifies all 71 deployed application/configuration hashes before
starting clients, refusing stale images, and has an explicit Redis-auth mode.
It independently checks unauthenticated PING rejection and authenticated PING.
The synthetic test password is not retained in result metadata.

Eight clients ran 90 measured seconds with 30-second rotations. All 638
commands reconciled exactly, 24 summaries finalized and 24 paused runs retained
their namespaces on one device without transient ownership. Client p95 was
209.5 ms, maximum 419.3 ms. These short overlapping memory windows are not a
replacement for the one-hour memory criterion.
Evidence: [source match](../evidence/reconciled_auth_load_20261017/image_source_match.json),
[Redis auth check](../evidence/reconciled_auth_load_20261017/redis_auth_verification.json),
[client result](../evidence/reconciled_auth_load_20261017/client.log),
[verdict](../evidence/reconciled_auth_load_20261017/result.json).
Current regressions: 270 Python passes, seven skips; 13 Rust passes, one opt-in
test ignored. CI Compose validation now supplies the required synthetic Redis
credential, and both base/managed Compose configurations validate quietly.
The reconciled authenticated candidate still needs its own completed long run.

October 19 review: `evidence/reconciled_auth_soak_20261017/result.json` is FAIL,
not still running. The host recorded clamshell sleep at 12:28:44 IST for 152
seconds and maintenance sleep at 12:31:27 for 142 seconds on October 17.
Attribution expired and sessions lost access; the hour must be repeated without
host suspension. The existing failure remains unchanged.

## October 19 authenticated ARM64 staging hour passed

The fresh candidate passed all eight client slots for at least 3,600 measured
seconds: 7,042 commands reconciled exactly with successful results and evidence
projections, 16 session summaries finalized, and 16 paused run namespaces remained
on one device with transient ownership removed. This retention check confirms
namespace presence and ownership cleanup, not byte-by-byte verification of every
historical file. Client p95 was 150.0 ms and maximum 665.5 ms. Across 595 samples,
the largest gap was 6.123 seconds; median core-memory growth was 52.45 MiB under
the predeclared 128 MiB bound, peak memory was 474.1 MiB, and there was no OOM.

Evidence is in `evidence/authenticated_soak_20261019_final`; the exact immutable
source and three image identities are linked from
[the October 19 verdict](RELEASE_EVIDENCE_INDEX_2026-10-19.md). The earlier two
October 19 attempts were deliberately interrupted while replacing vulnerable
infrastructure and making Redis explicitly non-root. Their failures and reasons
remain retained separately. This pass is for bounded private ARM64 testing, not
arbitrary attacks, indefinite retention or production capacity.
