# G6 recovery and capacity assessment — 2026-10-11

## Decision

**G6 passes for the documented eight-client Research MVP envelope.** The final image passed the full 60-minute deterministic workload, exact evidence reconciliation and the named restart/outage checks below. These results do not establish longer-duration or public operation.

## Environment and workload

Apple M4, 10 host CPU cores, 16 GiB host RAM, macOS 26.5.2; Docker Desktop 4.93.0, Engine 29.8.1, Linux arm64 kernel 7.0.14-linuxkit. Docker VM: 10 CPUs and 8,319,504,384 bytes RAM. Each tested core is limited to 2 CPUs, 2 GiB RAM and 192 PIDs. Redis uses a 256 MiB no-eviction limit; PostgreSQL and Redis otherwise share VM resources without separate CPU quotas. These are local containers on internal test networks, not distributed deployments.

The image is `apate-release:20261011`, manifest identity `sha256:37aedd15dbea3605ee60ca5a4e40e7ecf1e201472c114483a8bf02cb7ac314ee`. Every deployed application/configuration file matches the source. [Environment record](../evidence/release_checks_20261011/environment.json).

The sustained workload is eight client slots issuing `echo TOKEN > /tmp/probe; cat /tmp/probe; cat /etc/hostname`, with four seconds between sequences. It requires the exact token and hostname in the response. Each slot runs for at least 3,600 measured monotonic seconds, with no total-command early-stop cap. Connections rotate after 800 commands or 3,300 seconds, before the server's documented limits; planned rotations are counted separately. This measures an hour of service under eight client slots, not eight connections exceeding the one-hour policy.

The predeclared memory criterion is at most 128 MiB growth between the medians of the first and last 12 resource samples; peak memory and process count are reported separately. Raw samples permit inspection of growth before rotation as well as at the end. Command latency includes SSH response completion at the client; it does not measure real attacker engagement.

Idle sleep was prevented with `caffeinate -i`. Rust compilation occurred early in the run; separate short fault tests and the one-client comparison shared the Docker VM during part of the soak. Their start/finish intervals are retained in their run/result files. These measurements are engineering observations with disclosed co-resident activity, not uncontended hardware benchmarks.

## Current-image recovery results

| Fault | Reconciliation | Evidence |
|---|---|---|
| PostgreSQL paused for 31.2 seconds during an eight-client, 45-second workload | 1,400 submissions = 1,400 distinct successful results = 1,400 projected commands; 8 finalized summaries. Client p50 45 ms, p95 157 ms, maximum 241 ms. | [Client log](../evidence/recovery_postgres_20261011/client.log), [result](../evidence/recovery_postgres_20261011/result.json) |
| Whole core killed and restarted | All 150 client-confirmed commands present among 153 admitted attempts; all 8 original sessions closed as interrupted/orphaned; new session starts without old state. The three additional admitted attempts are not counted as client-confirmed execution. | [Client log](../evidence/recovery_core_20261011/client.log), [result](../evidence/recovery_core_20261011/result.json) |
| Redis stopped and restarted | All 129 client-confirmed commands present among 137 admitted attempts; all 8 original sessions reconciled as interrupted/orphaned; no inherited namespace on reconnect. The eight additional attempts are not assumed confirmed. | [Client log](../evidence/recovery_redis_20261011/client.log), [result](../evidence/recovery_redis_20261011/result.json) |

The default regression suite additionally exercises full-spool refusal before mutation, storage budgets, no-eviction Redis pressure, uncertain commits, mutation-journal replay and outbox crash recovery. It passed 244 tests with 7 explicit legacy infrastructure skips. The Linux/FUSE procedure passed real worker containment, isolation, handler/effect correlation and worker interruption. Physical host-disk exhaustion and simultaneous loss of all stores are not claimed by these fixtures.

## Soak record

[Run identity](../evidence/soak_20261011/run.json), [source hashes](../evidence/soak_20261011/source_hashes.json) and [raw samples](../evidence/soak_20261011/samples.jsonl) are retained. The final result must reconcile submissions, distinct successful results, projected commands, finalized sessions and removal of PID/namespace state. A live process, partial output, or missing final result never constitutes a pass.

The [client result](../evidence/soak_20261011/client.log) and [resource verdict](../evidence/soak_20261011/result.json) both pass. Run ID: `f769d6666bcb4e5296266c4326da7dda`.

| Measurement | Result |
|---|---|
| Actual duration per client slot | 3,600.005–3,600.007 seconds |
| Client slots / total sessions | 8 / 16, with one planned rotation per slot |
| Commands / audited submissions / distinct successful results / projected commands | 7,055 / 7,055 / 7,055 / 7,055 |
| Finalized summaries | 16; no remaining PID mappings or filesystem namespaces |
| Client response latency | p50 79.8 ms; p95 138.6 ms; maximum 407.7 ms |
| Resource samples | 578 |
| Initial / final median core memory | 423.25 / 465.20 MiB; growth 41.95 MiB |
| Peak core memory | 468.40 MiB |
| Initial / final median PIDs | 57 / 57; peak 61 during planned rotation |
| Core health | Running before harness teardown, no OOM |
| Cumulative core internal traffic | Docker reports about 449 MB received / 45 GB sent; coarse cumulative counters, not an external-network transfer |

The [one-client comparison](../evidence/load_single_20261011/client.log) passed 100/100 submitted, successful and projected commands with one finalized summary. Actual workload time was 24.24 seconds (the configured 60 seconds was an upper bound; the 100-command cap ended this short comparison). Latency was p50 41.8 ms, p95 51.4 ms and maximum 76.5 ms. Both measured client conditions meet the proposed one-second p95 target for this workload. Individual client-latency samples were summarized in-process; retained resource samples and command/server logs do not reproduce that client distribution independently.

Internal traffic is a material cost. The collector serializes the growing full summary to Redis for each event and periodically checkpoints it to PostgreSQL. Incremental projection/cache updates are a priority before broader concurrency or Home adaptation. The current resource and latency result does not establish that this architecture is economical for a lightweight sensor.

## Corrections and limits

Earlier attempts exposed missing attribution leases. Independent supervisor renewal now complements worker renewal. Both renew only an existing mapping owned by the same session while its lifecycle remains open. A missing mapping is not recreated: the namespace reaper may already have selected it for deletion. Tests cover wrong ownership, missing mapping and closed lifecycle. The rejected resurrection approach and its 35-minute test are historical, not evidence for this final image.

The worker has a separate bounded cumulative CPU allowance, default 300 seconds, configurable only within 60–600. No specific earlier failure is attributed to CPU exhaustion without exit-status evidence. Host/VM suspension can outlast a Redis lease; those sessions must fail closed, and suspended time is not valid continuous-service evidence. Earlier failures are retained as failures rather than relabeled passes.

The harness now records measured per-client duration, planned rotations and `scripted_test` origin, persists its artifacts independently of the chat terminal, and checks result/projection counts as well as submitted attempts. The nominal requested duration alone is insufficient evidence of the elapsed workload.

Eight clients are the supported measured envelope. The earlier 32-client PostgreSQL-outage run saturated and timed out clients; no 32-client service-level claim is made. The 60-minute result cannot establish multi-day reliability. Separate p95 outbox-visibility and summary-delay distributions are not measured by the final count check. Broader operations, field deployment and larger-scale projections remain future work.
