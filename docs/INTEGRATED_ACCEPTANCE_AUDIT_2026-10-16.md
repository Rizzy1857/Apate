# Integrated Research product acceptance audit — October 16, 2026

Target: a controlled local college/research product, not an internet-facing
production security appliance. Mirage Home remains separately deferred.

| Requirement | Evidence and current boundary | Verdict |
|---|---|---|
| GUI starts and stops its connected stack | Native startup/readiness, cancellation, missing-Docker display, owned-container cleanup and retained volumes verified October 15–16. Existing operator deployment was preserved during independent candidate checks. | Passed named procedures |
| Fake system is separate from runtime files | Real SSH/FUSE isolation and restricted-worker containment passed; loopback relay and internal core network inspected. This is a bounded emulator, not a full Linux VM or an absolute escape-proof guarantee. | Passed bounded contract |
| Persistent authoritative persona | Atomic per-profile device record and per-session snapshots; hostname, user, purpose and roles grounded in prompts. Snapshot identity retained across restart. | Passed named procedures |
| Persistent research runs | New shells default fresh; one-use operator resume restores files and cwd. Native crash/resume passed. Environment variables remain connection-local. | Passed named procedures |
| Live operations and honest health | Native contexts, generation activity, stale/disconnected states and database degraded/recovered display verified. Audit-view pause does not pause collection. | Passed named procedures |
| Research evidence exports | Native raw/redacted buttons passed hashes, private permissions and synthetic-sentinel disclosure checks. Admission-time runtime identity retained in historical exports. | Passed named procedures |
| AI behavior and claims | Deterministic mode remains default. Local model generation is bounded, validated and falls back; malformed history and truncation checks strengthened. Small model smoke trials include failures. No fine-tuning or hallucination-free guarantee. | Conditional capability, not AI-reliability certification |
| Persistent-run capacity and recovery | Eight-client short rotation workload and core/PostgreSQL/Redis fault checks passed. Extended soak failed after confirmed host lid-closure suspension outlasted attribution leases; original failure preserved. | Fresh uninterrupted one-hour soak required |
| Candidate packaging and image identity | Extracted-source arm64 bundle compiled, locally signed and verified. Uncached image application files matched archived source. Fresh core containment and offline scan completed. | Passed packaging/identity checks; not notarized |
| Security risk disclosure | Core scan retains 164 Debian matches, including 44 high; no fixed Debian versions listed. No broad public deployment or all-component clean-security claim. | Residual risk disclosed; controlled lab only |
| Final release identity | Candidate source/image identities retained. Packaging/harness/docs changes are reconciled in a separate handoff candidate; earlier archives stay immutable. Soak failure is not relabeled as accepted. | Final acceptance pending fresh soak |

Evidence sources: [native desktop verification](DESKTOP_VERIFICATION_2026-10-15.md),
[candidate index](RELEASE_EVIDENCE_INDEX_2026-10-16.md),
[persistent capacity checkpoint](PERSISTENT_CAPACITY_2026-10-16.md).

Completion must be stated against this scope. Do not mark the expanded product
complete solely because the older October 11 MVP passed its gates. Conversely,
do not silently expand this college MVP into Home deployment, universal attack
coverage, full POSIX compatibility, model training or production certification.

Resume authorization is an operator selection for the next shell, not a verified
participant identity binding. Any concurrent authenticated shell may consume the
one-use selection under permissive lab authentication. Arm it only while
controlling the next connection; it is not a safe multi-tenant identity mechanism.
