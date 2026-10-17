# Integrated desktop candidate evidence — October 16, 2026

Status: verified source candidate; final integrated-product acceptance pending.
This index is intentionally outside the source archive to avoid self-reference.

## Latest handoff candidate

The implementation, packaging safeguard, test harness and reconciled documents
are captured in `evidence/release_candidate_20261016_integrated_handoff`.
All 195 extracted source hashes and the archive hash were verified. Its extracted
Python suite passed 264 tests with seven explicit skips; Rust passed 12 with one
opt-in test ignored, reusing the existing target/dependency cache. Deployed
application/configuration files match the same fresh image assessed below.

- Source archive SHA-256:
  `f514a2bad18a8d8968db4bf1dff8e5499c7896f2c7a70a68880543610c290da1`.
- Manifest SHA-256:
  `b5c0e71df0388c2439ad5cacc341d913d01187ecd9f93c6bc09d26c600e440bc`.
- [Handoff verification](../evidence/release_checks_20261016/handoff-verification.json).

Final acceptance is withheld, not silently waived: the extended soak failed
after macOS recorded Clamshell Sleep at 10:41:32 IST for 145 seconds. The
149-second resource-sample gap exceeded the 120-second attribution lease, and
all eight sessions failed closed. See the retained
[diagnosis](../evidence/persistent_soak_20261016/diagnosis.json).
The harness removed its disposable containers; no operator data was deleted.
A fresh uninterrupted hour with the lid open, host awake and Docker running
is required before a complete extended-capacity verdict. No commit or push was
performed in this closeout. Earlier candidate identities below remain historical.

## Candidate identity

- Bundle: `evidence/release_candidate_20261016_desktop_v2`.
- Base commit: `32354d24a55c9edb93d0440fa284b4099e9dcd67` plus the
  complete archived working-tree source, including untracked implementation.
  The base commit or tracked patch alone does not identify this candidate.
- Source archive SHA-256:
  `91a61a54eb5a4c2e79c9ed907f63bea83a8e4ec9d52489063cb88a7fbe8030c6`.
- Source manifest SHA-256:
  `d48ab8d000185732d0ef257d2de45411b3d341a8a8690e70a049469f7e5cf9de`.
- 190 extracted source files individually matched the manifest hashes.
- Image inventories and the fresh scan are attached separately below. No
  bit-identical future rebuild or dependency-safety conclusion is implied.

## Verification

The extracted v2 candidate passed the default Python suite: 262 passed, 7 explicit
skips. Its Rust invocation passed 12 tests with 1 opt-in real-core test ignored.
Rust reused the existing dependency/build cache; this is not a clean-room build.
The working tree additionally passed all four explicit real-HTTP inference
deadline/classification tests. See
[today's checkpoint](INTEGRATED_VERIFICATION_2026-10-16.md) and
[native desktop checks](DESKTOP_VERIFICATION_2026-10-15.md).

The earlier `release_candidate_20261016_desktop` remains preserved: extracted
Python passed, but Rust exposed an immediate lock-reacquisition timing failure.
V2 bounds the recovery assertion to two seconds while retaining exclusivity
checks. No production lock checks were relaxed.

One synthetic local notes request completed with 60 output bytes and passed the
validator. Earlier six-artifact trials still contain generation failures.
This is not sufficient evidence of AI reliability, realism superiority or
hallucination-free content. Default deterministic mode remains unchanged.

## Packaging and image follow-up

Packaging from the extracted candidate succeeded with a new Rust target
directory. The arm64 macOS bundle passed strict ad-hoc signature verification
and plist lint. Executable SHA-256:
`b3f086d5d74a21770615dc7a0f3ec452116f0e5658e3478a5348bb6c375f4797`.
This is a local development app, not a notarized distributable. It was not
launched in this checkpoint because the operator GUI was already running.
The extracted-directory Rust suite also passed (12 passed, 1 ignored), without
reusing the working tree's target directory. The extracted Linux/FUSE integration
suite passed in uniquely named disposable containers; the active GUI was not
stopped or reconfigured.

A separate `docker build --no-cache` succeeded and upgraded 16 Debian packages.
The [fresh-image inventory](../evidence/release_candidate_20261016_desktop_fresh_image/image_inventory.json)
verifies deployed application hashes against the identical v2 source archive.
Manifest-list identity:
`sha256:ef06e47e54a387266a11401aac9fe92caf98bd0809c9a70b01aea16205107de4`.
Configuration identity:
`sha256:db2fe43c6da29c77e458a5430b63c8bf6bbf8d9eb734dfdb0f12df2f272dcb74`.
The fresh image separately passed restricted-worker containment. The full Linux
harness completed before this uncached image was ready, so its pass is not
misattributed to the upgraded image.

The [Trivy report](../evidence/release_checks_20261016/trivy-fresh.json) used
scanner 0.69.3 pinned to digest
`sha256:bcc376de8d77cfe086a917230e818dc9f8528e3c852f7b1aff648949b6258d1c`.
Its database was updated October 16 at 01:13 UTC and downloaded separately
without mounting project data. The image scan ran with networking disabled,
offline scanning, database updates disabled and telemetry disabled. No source
or package metadata was uploaded to a scanner service.

Results: zero Python findings; 164 Debian package/advisory pairs across 71
identifiers (0 critical, 44 high, 58 medium, 61 low, 1 unknown). None has a fixed
Debian version listed in this database. These are unresolved scanner matches,
not demonstrated exploit paths or proof of non-exploitability. Updated packages
did not eliminate the reported residual risk. This is not a clean security bill.
Exact identities and checks are in
[verification.json](../evidence/release_checks_20261016/verification.json).

## Remaining acceptance work

### Residual security disposition

The refreshed scanner's (ecosystem, advisory identifier, package, severity)
matches are identical to the October 11 report: zero added and zero removed
matches. This comparison does not establish unchanged exploitability or replace
review of updated package versions.

A read-only executable inventory of the fresh image found no systemd-homed.
It did find mount/umount/su with setuid bits, plus nsenter, login, perl, tar and
infocmp. Their presence is retained as a risk, not dismissed because the
participant command registry emulates commands. The restricted worker's chroot,
zero effective capabilities, no-new-privileges and denied exec/process/socket
operations reduce direct participant access, and containment tests passed.
The trusted FUSE/core process still needs substantial container privileges;
compromise of that process is not covered by the worker-only argument.

Disposition: retain the upgraded baseline for controlled local lab evaluation
only, with all scanner matches disclosed. Do not label these findings patched,
false positives or universally non-exploitable. Public/untrusted deployment is
not approved by this checkpoint. Before a broader release, reassess fixes and
privilege reduction, rescan the actual delivered images, and review trusted
process and dependency attack surfaces. The scan covers the Python core image,
not the native Rust lockfile, relay/base image, Redis, PostgreSQL, host or Docker
kernel. A comprehensive all-component security assessment remains outside this
single-image result.

See the [requirements-to-evidence audit](INTEGRATED_ACCEPTANCE_AUDIT_2026-10-16.md)
and [persistent-run capacity checkpoint](PERSISTENT_CAPACITY_2026-10-16.md).
The eight-client short workload and core/PostgreSQL/Redis fault checks passed;
the interrupted first Redis fixture is preserved separately as incomplete.
Extended soak and final source/evidence reconciliation remain. Any broader
security certification needs an all-component review, not this core-only scan.
Preserve the incomplete attempts, failed trials and residual risks.

The one-hour persistent-run soak under `evidence/persistent_soak_20261016`
failed after confirmed host lid-closure suspension outlasted attribution leases.
It is retained as failed, not counted as continuous-service evidence. A fresh
hour with the lid open, host awake and Docker running is required. Current
working-tree regressions are 264 passed, seven explicit skips after adding a
Docker build-context exclusion guard for private deployment data/operator
outputs. Application/configuration hashes still match the tested image. These
later packaging/test/docs changes are captured separately in the handoff
candidate below; they are not silently attributed to the earlier v2 archive.
The historical October 11 MVP release is not silently promoted to certify this
expanded product. Mirage Home and model fine-tuning are not delivered here.
