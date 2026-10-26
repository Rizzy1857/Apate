# ARM64 image refresh — October 23, 2026

This review updates the [October 19 assessment](DEPLOYMENT_SECURITY_REVIEW_2026-10-19.md) for the same private, authorized disposable-VM scope. Current database scans exposed fixable issues in the old images, so new images were built without cache before handoff. Application behavior is unchanged; trust-store and OS dependencies changed and require fresh runtime checks.

## Findings remediated

The old core's certifi 2026.10.18 matched critical advisory [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2), which identifies 2026.10.19 as patched. `requirements.txt` now pins that version. The rebuilt core confirms it is installed. Debian [DSA-6572-1](https://security-tracker.debian.org/tracker/DSA-6572-1) identifies a fixed trixie CA-store package; the existing apt-upgrade build step fetched current security packages.

Old Redis/PostgreSQL images each acquired two UNKNOWN-severity musl package matches with available fixes. Uncached Alpine upgrades applied musl 1.2.5-r12 for Redis and 1.2.6-r3 for PostgreSQL, along with same-release security updates. Explicit non-root image users remain unchanged.

## Current scans

| Image | Immutable local identity | Current findings |
|---|---|---|
| Core | `sha256:6fdfd9306a388e2197709d48e07ff60a5440d84b86d60a5a1db2576266b7167a` | 164 package/advisory pairs: 44 HIGH, 58 MEDIUM, 61 LOW, 1 UNKNOWN; zero CRITICAL and zero Python findings |
| Redis | `sha256:92cef1632d794407cf5e16b76b40f72c1aa9858754712afd6130f65b34411182` | No known findings |
| PostgreSQL | `sha256:6c97731c044b0ce2f874e93be5314c5f461ff1882030e4e9c7280b37bc676558` | No known findings |

All are Linux ARM64. Local image IDs are not registry publication digests. Trivy 0.69.3 uses pinned scanner digest `sha256:bcc376de8d77cfe086a917230e818dc9f8528e3c852f7b1aff648949b6258d1c`; its freshly downloaded DB was updated October 23 at 01:18:09 UTC. Networking was disabled for image scans. The separate DB-download container mounted only its cache; scans mounted exported images and their new private evidence directory, with no repository or Docker socket. Findings were not filtered by severity/fix availability. Scanned filesystem DiffIDs matched each inspected image.

Private full reports and manifests are under `evidence/deployment_gates_20261023_updated`; the before-remediation reports remain under `evidence/deployment_gates_20261023`. `tests/integration/scan_release_images.py` reproduces the procedure. Completion means scanned, not risk approval.

## Residual disposition

The rebuilt core has the same unique advisory set as the October 19 report, including the same eight HIGH identifiers; none is newly suppressed. Its UNKNOWN match is [CVE-2026-82560](https://security-tracker.debian.org/tracker/CVE-2026-82560), a Perl Pod::Text resource-exhaustion issue. Debian lists the source package as affected; a read-only probe finds no Pod::Text module in the runtime. Preserve the package finding rather than calling the image universally unaffected.

The existing privileged-core/FUSE risk remains. Prior private-testing acceptance does not authorize public exposure. Infrastructure scan results apply to the rebuilt staging images, not the desktop/base Compose's older images. Azure/host software, design flaws and future advisories remain outside these image scans. A rebuild, later DB refresh or broader exposure needs its own review.

Linux isolation/audit recovery, backup/restore and bounded storage faults passed against the rebuilt images. The authenticated hour failed after laptop suspension; a continuously awake rerun is required before final handoff. See the [current release index](RELEASE_EVIDENCE_INDEX_2026-10-23.md).
