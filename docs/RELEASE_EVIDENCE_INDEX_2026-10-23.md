# ARM64 release candidate — October 23

Current state: source frozen, security refresh complete, Linux integration and operational recovery passed; the rebuilt image's authenticated hour **failed after host suspension**. Final deployment handoff is blocked pending an uninterrupted rerun. Private authorized disposable-VM scope remains unchanged. Registry publication and Azure deployment have not occurred.

## Candidate identity

Frozen evaluation source: `evidence/release_candidate_20261023`, based on commit `3892df8a7f590c3378c92edd470d3e74e0d9c395` plus its archived working-tree changes. All **210 extracted file hashes verified** before execution.

- Archive SHA-256: `5bd9eb1a25a61a3e84f7b11ed0776a8b8b8899022f87d1527bc7e8b92e1f4bec`.
- Manifest SHA-256: `6485b7152102347934ca472895564fa28bfa5acf8336e560ea400f249c45f187`.
- Core: `sha256:6fdfd9306a388e2197709d48e07ff60a5440d84b86d60a5a1db2576266b7167a`.
- Redis: `sha256:92cef1632d794407cf5e16b76b40f72c1aa9858754712afd6130f65b34411182`.
- PostgreSQL: `sha256:6c97731c044b0ce2f874e93be5314c5f461ff1882030e4e9c7280b37bc676558`.

The freezer verifies application/configuration hashes against the core image. These local image IDs are not registry digests. Before publication, retain exact IDs and scanner metadata; after publication compare ARM64 image configuration digests and filesystem DiffIDs as well as the registry manifest. Docker Desktop and other engines can expose different types of digest as `.Id`.

## Verification

| Check | Current result |
|---|---|
| Python regression | 304 passed, seven explicit infrastructure skips |
| Locked Rust suite | 13 passed, one opt-in integration check ignored |
| Rebuilt-image Linux integration | Passed worker confinement, real SSH/FUSE, isolation, worker termination, audit outage/uncertain-commit recovery and export reconciliation |
| Rebuilt-image operational drill | Passed cold backup/restore, persona/cwd/marker/host-key retention, 11 baseline audit IDs, pending-event replay exactly once, both export modes, tmpfs ENOSPC and Redis capacity recovery; cleanup succeeded |
| Current vulnerability database | Critical certifi/CA-store/musl updates remediated; zero critical/Python findings; core retains 44 HIGH, 58 MEDIUM, 61 LOW and one UNKNOWN; Redis/PostgreSQL have no known findings |
| Authenticated eight-client hour | FAILED: host clamshell/maintenance sleep exceeded the attribution lease; no completed one-hour verdict |

New-image operational evidence: private `evidence/operational_readiness_20261023_updated`. It contains credentials/backups and must remain ignored. Full scan evidence: private `evidence/deployment_gates_20261023_updated`. Python/Rust/Linux terminal results are retained in the task transcript.

The hour writes `evidence/authenticated_soak_20261023`: 3,600 seconds, eight slots, four-second command interval, Redis authentication and persistent runs enabled. The host is kept awake with `caffeinate -i`. The preflight matches the image to the frozen source. Do not replace this run's workload or source while it is running; failed/interrupted runs remain failures. Final acceptance must reconcile client duration, submitted commands, audit/result/projection counts, finalized sessions, retained namespaces, sampling/memory bounds and cleanup.

The run started at 06:23:04 UTC and ended failed at 06:54:46 UTC. Only 153
resource samples were recorded; gaps of 307.943 and 675.777 seconds interrupted
continuous operation. macOS power logs show clamshell sleep at **12:07:58 IST**,
dark wake at 12:13:02, maintenance sleep at 12:13:08 and lid wake at 12:24:20.
These align with the sample gaps. The independent 120-second worker leases
expired, and workers refused expired attribution. Clients then observed denied
filesystem operations or disconnections. This failure does not establish full-hour
capacity or complete audit reconciliation.

The failure and logs are retained. Docker inspection confirmed no containers
from owned prefix `apate-load-6087755948` remained after cleanup. No attribution
TTL was increased and no failure was relabeled a pass. `caffeinate -i` prevents
idle sleep; it did not prevent this lid-triggered suspension. Keep the Mac awake
with its lid open throughout a retry, or use a continuously running Linux host.
An unattended retry on the same suspendable host requires that operating
condition first. The completion heartbeat was removed after reporting the
required user action.

The [October 19 hour](RELEASE_EVIDENCE_INDEX_2026-10-19.md) remains historical evidence for the earlier images. The [desktop walkthrough](OPERATIONAL_READINESS_2026-10-23.md) passed on the managed development graph; its base infrastructure does not inherit the hardened staging scan result.

## Deployment handoff

Use the [updated security review](DEPLOYMENT_SECURITY_REVIEW_2026-10-23.md), [operations runbook](OPERATIONS.md) and [Azure staging guide](AZURE_STAGING.md). The local Azure CLI is unavailable, and no target subscription/resource group/region/registry/VM has been supplied. Those destination details are required before publishing or provisioning.

After the hour passes, reconcile current docs and make a final handoff freeze. Its runtime application/configuration and workload files must match this tested candidate; documentation-only differences must be recorded. Freeze evidence remains local/private by default under the repository's ignore policy.
