# ARM64 staging image security review

This review supports private authorized testing on a dedicated disposable ARM64 Linux VM, not unrestricted Internet exposure. The core retains unresolved OS-package findings and privileged FUSE requirements. The human operator explicitly accepted that restricted scope on October 19; the decision is retained in `evidence/deployment_gates_20261019/operator-risk-acceptance.json`. A successful functional test is not a security waiver.

## Images and scan scope

The three candidate images were scanned offline with Trivy 0.69.3, scanner digest `sha256:bcc376de8d77cfe086a917230e818dc9f8528e3c852f7b1aff648949b6258d1c`, and vulnerability database updated October 19 at 07:19:54 UTC. The database was downloaded separately without source mounts. Scans used networking disabled, vulnerability scanning only, updates disabled, no ignored/unfixed filtering and no telemetry. Scanner metadata, image identities and full findings are in `evidence/deployment_gates_20261019`.

| Candidate | Immutable local image identity | Findings |
| --- | --- | --- |
| Core | `sha256:ac671e6fe7797039c8f787edff3ba977293b6dd44c7dd921b1f5e475e38346d8` | 164 OS-package/advisory pairs: 44 high, 58 medium, 61 low, 1 unknown; no critical or Python findings |
| Updated non-root Redis | `sha256:b5e97ff80e21bec8306ef3c9bf26c1d2fd6926b476c162a3641599aed20ac06c` | No known findings in this scan |
| Updated non-root PostgreSQL | `sha256:2fcb9cef6f472fbf055a04dc6b8318dd4d47ddb5486ab9379bf8ed6436d33eee` | No known findings in this scan |

Local image identities are not registry publication digests. Record registry digests after publication and verify their architecture, configuration and layers match these tested images. The scan does not cover Azure, the host kernel, Docker Engine, runtime secrets, application design flaws or the macOS console. A clear report is not proof of vulnerability absence. The scanner warns that its EOL catalogue does not list Alpine 3.24; PostgreSQL package scanning completed, but this warning is not lifecycle certification.

## Infrastructure findings remediated

The original pinned Redis scan reported 190 package/advisory pairs, including six critical and 70 high; PostgreSQL reported 141, including three critical and 46 high. The full before reports remain retained. Current same-major official images were evaluated before building the staging variants. Redis still needed OpenSSL and zlib package updates. PostgreSQL still needed a zlib update and contained the Go-built gosu helper.

`Dockerfile.redis` updates same-release Alpine packages. `Dockerfile.postgres` updates packages, removes gosu and starts as the postgres user. This avoids using a blanket suppression for Go findings: the helper is absent from the resulting filesystem. The [gosu security policy](https://github.com/tianon/gosu/blob/master/SECURITY.md) distinguishes library-version matches from vulnerable-function reachability, but no such assumption is needed to exclude the removed executable. PostgreSQL fresh named-volume initialization and the Linux integration suite passed with this variant. Root-owned bind mounts and silent upgrades of existing database volumes are not supported by this change.

Redis explicitly starts as redis, including when Compose invokes a shell; the image does not rely on the entrypoint to switch users for that command.

These variants apply to `compose.azure-staging.yml`, not the older managed desktop/base Compose infrastructure images. Do not transfer their clean scan result to those older images.

## Core high severity findings

There are eight unique high-severity identifiers across 44 package/advisory pairs. Debian's stable trixie tracker still lists the affected source versions as vulnerable; fixed unstable versions are not a supported drop-in upgrade for this image. No fixed trixie version is listed in the scan. Do not mix unstable packages into this release merely to remove scanner matches.

| Advisory | Affected functionality and review boundary |
| --- | --- |
| [CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642) | util-linux privileged post-mount hooks after helper failure. mount is present and setuid; no patch claimed. |
| [CVE-2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408) | nsenter cgroup authority leakage. nsenter is present; do not use privileged namespace tools against participant-controlled targets. |
| [CVE-2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409) | util-linux detached-tree subdirectory resolution. Do not authorize participant-supplied fstab entries or mount options. |
| [CVE-2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410) | restricted bind-mount source redirection. No host research-content bind mounts are allowed by the staging configuration. |
| [CVE-2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369) | libacl pathname APIs can follow attacker-controlled symlinks in a privileged caller. Application source has no explicit libacl calls; that is not a complete native-library reachability proof. |
| [CVE-2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720) | infocmp stack overflow. infocmp is present; participant commands do not execute this CLI. |
| [CVE-2026-16742](https://security-tracker.debian.org/tracker/CVE-2026-16742) | systemd-homed privilege escalation. Read-only inventory found no systemd-homed executable; shared systemd libraries still produce scanner matches. |
| [CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) | Perl Archive::Tar memory exhaustion. perl-base is installed, but loading Archive::Tar fails because that module is absent. The package-level match is preserved. |

## Containment and residual risk

The Linux checks confirm worker chroot, UID/GID 1000, zero effective capabilities, no-new-privileges, seccomp filtering, rejected execution/forwarding requests and cross-session isolation for the tested cases. The command registry emulates commands rather than launching host programs. This restricts direct participant access to the listed CLI paths; it does not establish that every exploit path is unreachable.

The trusted core runs outside that worker boundary with SYS_ADMIN, SYS_CHROOT, SETUID, SETGID and KILL, plus an unconfined AppArmor profile for FUSE. A core compromise can invalidate the worker-only argument. Keep the VM isolated from valuable systems, identities and networks; retain loopback-only research ingress, the internal container network, read-only core root filesystem, resource limits and no Docker socket mount. Do not widen exposure on the strength of this review alone.

Before public or untrusted access, resolve or explicitly accept the remaining advisory risks through a separate threat review, reevaluate core privilege separation, and rescan the actual published images with current data. Private staging acceptance must be recorded separately from the scanner result.
