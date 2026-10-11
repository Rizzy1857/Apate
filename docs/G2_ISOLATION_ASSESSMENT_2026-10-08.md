# G2 isolation assessment — 2026-10-08

## Decision

G2 passes for the Research MVP's declared Linux-container boundary. This decision is limited to the emulated SSH command surface and the named containment tests; Mirage is not a malware sandbox and does not expose arbitrary participant code execution.

## Exercised boundary

The disposable Linux integration starts two simultaneous real SSH sessions backed by separate Redis filesystem namespaces. It verifies:

- the same `/tmp/secret` path holds different content in each session;
- neither session can read the peer's content or discover the peer's filename through directory listing;
- removing one session's file does not remove or alter the peer's file;
- the same environment-variable name retains a different value in each worker;
- absolute and relative `..` traversal remain within the virtual root;
- container runtime files and procfs are absent from the participant namespace;
- writes, creates, directory creation, removal, copy and move into protected profile paths fail;
- failed protected-path moves do not remove the source file;
- participant-owned paths remain writable;
- killing one restricted worker closes only its session while the peer remains functional.

The containment check additionally verifies a chrooted UID/GID 1000 worker cannot see `/app/requirements.txt`, regain UID 0, create a socket, fork or execute a program. Live worker `/proc` state verifies zero effective capabilities, `NoNewPrivs=1` and seccomp filter mode 2. The container itself runs read-only with bounded temporary filesystems, dropped capabilities except those required by the privileged FUSE/core process, an internal Docker network, PID/memory/CPU limits and no-new-privileges.

## Result

`bash tests/integration/run_linux.sh` completed successfully on Docker Engine 29.8.1. The deliberate PostgreSQL connection failures in its recovery phase are fault stimuli; retained events reconciled before the harness passed.

No cross-session disclosure or mutation occurred. No forbidden capability succeeded in the tested worker boundary.

## Limitations

- The privileged core/FUSE process, Linux kernel, Docker engine, Redis and PostgreSQL remain trusted infrastructure.
- The worker retains the already-open Redis connection needed for emulation after new socket creation is blocked. The participant command registry exposes no arbitrary Python or host execution path; this test does not claim safety if trusted interpreter control is compromised.
- The check is not a kernel exploit, container escape or malicious-binary evaluation. Arbitrary execution and malware detonation are explicitly outside the MVP.
- Session isolation is application namespace isolation inside one deployment, not public cloud multi-tenancy.
- Future commands, filesystem operations or privilege changes require the G2 matrix to be rerun and extended before release.

## Reproduction

Run `bash tests/integration/run_linux.sh` on a disposable Docker host with Linux FUSE support. The harness owns uniquely named containers, an internal network and a temporary image and removes them on exit.
