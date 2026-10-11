# G7 release assessment — 2026-10-11

## Scope and decision

The core image vulnerability assessment is complete. The final G7 decision and source-freeze/extracted-copy results are recorded in the [current release evidence index](RELEASE_EVIDENCE_INDEX_2026-10-11.md). This assessment supports the contained, local college Research MVP only. It does not certify public deployment, arbitrary execution, or Mirage Home.

The fresh dependency installation succeeded on Docker Desktop arm64. The final core image excludes the separately built Rust console and deferred Layer 0 source through `.dockerignore`. Neither directory is imported by the Python runtime. The initial scan found five advisories in the unused Layer 0 lockfile; exclusion removes those unused inputs from the deployed image, but does **not** repair the experimental Layer 0 repository. Layer 0 requires its own dependency upgrade and evaluation before activation.

## Reproducible scan record

- Scanner: `aquasec/trivy:0.69.3`, registry digest `sha256:bcc376de8d77cfe086a917230e818dc9f8528e3c852f7b1aff648949b6258d1c`.
- Database updated: `2026-10-11T01:13:45.784565337Z`; downloaded: `2026-10-11T03:15:44.778302627Z`.
- Image tag: `apate-release:20261011`; local manifest identity `sha256:37aedd15dbea3605ee60ca5a4e40e7ecf1e201472c114483a8bf02cb7ac314ee`.
- Scanned image configuration identity: `sha256:30008a89808c2360abaadfc93cf411355cf810a5b873cbb22fb79153283be29e`. Manifest and configuration hashes describe different OCI objects.
- Report: [trivy-final.json](../evidence/release_checks_20261011/trivy-final.json). Initial, superseded scan: [trivy.json](../evidence/release_checks_20261011/trivy.json).
- Database download received no project inputs. The actual scan used `--network none`, a read-only local image archive, `--offline-scan --skip-db-update --skip-java-db-update --skip-version-check --scanners vuln` and disabled telemetry. Project/package metadata was not submitted to a remote scanner.
- Reproduction follows the documented [Trivy image scan options](https://trivy.dev/docs/v0.69/guide/target/container_image/). Download a current database separately, export the image with `docker save`, then scan the archive with networking disabled. A later database may report different findings.

## Findings and disposition

The report contains **164 Debian package/advisory pairs across 71 distinct identifiers**: 0 critical, 44 high, 58 medium, 61 low and 1 unknown. These are package-level matches, not 164 demonstrated exploit paths. All have no fixed Debian package version listed in this database. The image was rebuilt after `apt-get update` and `apt-get upgrade`; an empty fixed-version field does not prove a fix is impossible or that an advisory is harmless. The Python-distribution scan reports zero known findings. The interpreter is Python 3.11.16; distribution scanning is not a complete audit of the interpreter, bundled native libraries or host kernel.

The 44 high matches collapse to these eight identifiers. They remain visible in the report; no ignore file or severity suppression was used.

| Advisory | Relevant path and bounded disposition |
|---|---|
| CVE-2025-69720 | Describes `infocmp` input handling. The emulator does not execute native terminal tools; worker exec is denied. Retain as an image risk for trusted native-tool use. |
| CVE-2026-16742 | Describes `systemd-homed`. The image has systemd libraries, but a direct image check found no `systemd-homed` executable. No homed-managed login is part of this deployment. Retain the source-package match without claiming the installed libraries have been exhaustively audited. |
| CVE-2026-54369 | Describes pathname-based libacl operations by a privileged caller. The emulator's filesystem permissions are implemented in Redis/FUSE, and it does not invoke libacl ACL operations. The trusted core remains privileged, so this is a residual infrastructure dependency risk. |
| CVE-2026-76642 | Describes external mount-helper failure and privileged post-hooks. Participants cannot execute mount helpers or select host mount options. Core startup mounts the configured FUSE path. Retain the advisory for privileged operator use. |
| CVE-2026-78408 | Describes `nsenter --join-cgroup`. No such operator command is used in Mirage; worker namespace changes and exec are denied. Retain for trusted administration outside the tested workflow. |
| CVE-2026-78409 | Describes `X-mount.subdir` traversal. No participant-controlled fstab entries or those options are provided. Retain for host/container administration. |
| CVE-2026-78410 | Describes restricted bind mounts with ownership/mode post-options. Those options and attacker-controlled host mount sources are absent from the supported workflow. Retain as an infrastructure risk. |
| CVE-2026-9538 | Describes Perl `Archive::Tar`. An image check could not import `Archive::Tar`; the emulator does not execute Perl or process real attacker archives. Retain the source-package match. |

All remaining medium/low/unknown matches are retained in the raw report. They include libc, SQLite, PAM, archive tools and compression libraries. Some libraries are used by the trusted application, so lack of native participant execution is **not** a blanket non-exploitability argument. The current disposition is to retain the upgraded Debian baseline for this bounded lab workflow, monitor upstream fixes before the next release, and rerun the scan after dependency changes. No blanket false-positive or patched claim is made.

The verified worker boundary is chroot, UID/GID 1000, no effective capabilities, no-new-privileges and seccomp denial of exec, new sockets, process creation and namespace/mount operations. The Compose boundary adds a read-only root, explicit capabilities, resource limits and loopback publication. These reduce exposure; they do not remove vulnerabilities from the trusted core or host. Public deployment and native attack execution remain outside the release scope.

## Remaining release evidence

The Linux/FUSE regression passed on 2026-10-11; its fault-injection errors and final pass messages are retained in [linux.log](../evidence/release_checks_20261011/linux.log). The Python suite passed 244 tests with 7 explicit infrastructure skips. The native console's prior G4 walkthrough remains applicable only if its files match the verified predecessor. Final candidate hashes, that comparison, extracted-copy checks and the G6 verdict belong in the current release evidence index.
