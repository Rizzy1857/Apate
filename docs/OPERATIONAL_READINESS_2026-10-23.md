# Operational readiness — October 23, 2026

Scope: private ARM64 research staging on local Docker Desktop, followed by the native macOS development application. No Azure resource was created or image published. This extends [October 22 behavioral checks](WORKING_REVIEW_2026-10-22.md); it does not replace the dated vulnerability assessment or authorize public exposure.

## Cold restoration and bounded storage faults

The new `tests/integration/verify_operational_readiness.py` owns unique source/restore Compose projects. It copies Redis, PostgreSQL and the audit-spool volumes only after stopping all writers, retains the original volumes until verification finishes, and restores to new volumes with the same images. Credentials and tar archives remain inside a mode-0700 ignored evidence directory; credential/archive files use mode 0600. Never publish that directory.

The restored stack verified stable persona, the SSH host key, saved cwd and marker file, preservation of the original 11 audit event IDs, delivery of a deliberately pending durable outbox event exactly once, and raw/redacted export contents and hashes.

Initial harness attempts are retained as failures: an unsupported `Path.open(opener=...)` call, an export snapshot requested inside an existing verification transaction, and an attempted `docker compose cp` from tmpfs. The first two were harness defects. The tmpfs copy behavior also affected the operator guide, which now streams archives through container exec. No application source changes were needed for these findings.

The bounded storage checks exercise actual `ENOSPC` in a dedicated 4 MiB tmpfs, then verify SQLite integrity, retention of a previously acknowledged event, rejected admission while full and successful admission after space is released. A separate 8 MiB Redis no-eviction instance must refuse new writes, retain an acknowledged key and accept writes after pressure is removed. These tests do not fill the workstation disk.

Focused existing regressions: **40 passed** across storage admission, hardening, report/export reconciliation and persistent-run controls. The macOS development app rebuilt and ad-hoc signing completed successfully.

## Final observed results

The combined local drill **passed** in private ignored directory `evidence/operational_readiness_20261023_complete`:

- Persona, SSH host key, marker bytes and `/tmp` cwd restored successfully.
- All 11 baseline audit event IDs survived; the deliberately pending outbox event was delivered exactly once.
- Raw and redacted exports passed content/hash checks and were archived to the host through exec.
- Actual tmpfs ENOSPC rejected the new event, retained prior data, passed SQLite integrity checks and recovered after freeing space.
- Redis no-eviction capacity pressure rejected writes, retained the acknowledged key and recovered after pressure was removed.
- Source/restore containers, networks and disposable volumes were cleaned up successfully.

The intermediate `verified` attempt exposed buffered filler writes raising ENOSPC on close; unbuffered writes fixed the fault-injection harness. Failed attempts remain recorded as failures. The final result includes the complete corrected sequence.

Native desktop checks passed: automatic startup/readiness, visible healthy
collection with zero pending events, two live sessions showing distinct `/tmp`
and `/home/ubuntu` directories, session file isolation, GUI-selected resume with
retained marker/cwd, GUI-selected fresh run, finalized history/detail, and both
GUI export buttons. The two host export bundles contain 13 hash-verified members
with mode-0700 directories and mode-0600 files. The synthetic seed run was
`9e5543be-bc84-43cb-bcb6-700940dc97ff`; the resumed session was
`3811a732-1e54-49ce-b5f7-432d5aea26ac`.

Normal quit removed all four managed containers while retaining the four named
volumes. Relaunch reached healthy readiness with zero pending audit events. A
second GUI-selected resume recovered the same marker and `/tmp` cwd in session
`b6bbbc6f-1fa9-43f1-9eda-4a55ab22549a`. The app was then quit normally.

Reproduction identity: checkout parent `3892df8`, with the new harness and
documentation changes in the working tree. Harness SHA-256:
`75ec2ddf686594e05abe0a930c0428f742ec8550e985682afa56a0ac926910b8`.
Combined `result.json` SHA-256:
`83ee6837279e3dd2cf2226bf0bd463d6d7beac8f0dbf76a56f2166c9ddd4014e`.
The manifest retains exact image IDs; the tested staging core was
`sha256:ac671e6fe7797039c8f787edff3ba977293b6dd44c7dd921b1f5e475e38346d8`.
Desktop development uses the base Compose infrastructure images and therefore
does not inherit the hardened staging images' vulnerability-scan verdict.

## Remaining deployment conditions

- Repeat host-dependent checks on the intended ARM64 Azure VM: FUSE/kernel support, authentication, loopback tunnel and NSG behavior, exact image identities and recovery.
- Physical volume restoration has the same image/platform/database-version requirement. Cross-version PostgreSQL migration is outside this drill.
- Host power loss, PostgreSQL disk exhaustion, full host-disk exhaustion, off-host encrypted backup delivery and multi-day retention remain separate cases.
- Image rescanning, immutable registry publication, real storage alerts, evidence retention policy and budget alert configuration are required deployment work. The October 19 scan remains dated evidence.
- Existing core residual risks and the scoped private-testing acceptance still apply. Home and model training remain separate workstreams.

Use [OPERATIONS.md](OPERATIONS.md) for backup, restore, storage incidents and reproduction commands.
