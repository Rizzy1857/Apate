# Release evidence index — 2026-09-29

This index identifies the current Mirage Research MVP candidate after command-stage and real SSH request verification. It supersedes the 2026-09-28 candidate for current testing without deleting that historical bundle. It does not declare every release gate passed.

## Candidate identity

- Frozen bundle: `evidence/release_candidate_20260929/`
- Base commit: `a098fe02771802de03b9c64c8fbce52d82defc38`, plus the working-tree files captured by the archive and tracked patch
- Source archive: `source.tar.gz`, SHA-256 `923bbe36424f818ee643129e3c18a67df8a18ea81e3f43dea9afefea1543ba74`
- Source manifest: 158 files, SHA-256 `7d19992657bed7fb27a5b7695df26b2c0c040323601bf5134cb1b0dfa54a46b1`
- Candidate record: `candidate.json`, SHA-256 `d1860db1fda224b967a24bf9abc020022f7abc9c336b12afbbb61643cb442e62`
- Completion record: `complete.json`, SHA-256 `0f8d7f72e192d25f9bfae23f2998b6d5b9a89ac281a482de6852f6f681901e24`
- No-cache image identity: `sha256:4ce4b5f401ab8bb94821eba62e8a4bb9d0e87c8656b3f103b7e5dc41b67101a6`
- Resolved inventory: 91 Debian packages and 26 Python distributions; inventory SHA-256 `c1bab078c3b438b9d524d0f749d391b429a89d906da0578f4a26a9d8586c1849`

Release evidence indexes are deliberately excluded from their own source archive to avoid self-referential hashes. Generated evidence, caches, Rust build output, bytecode and `.DS_Store` are also excluded. Every archived member is individually hashed.

## Verification record

| Check | Result | Scope |
|---|---|---|
| Python suite | 134 passed, 7 skipped | Default suite; legacy infrastructure skips are not passes |
| Linux SSH/FUSE integration | passed | Password/public-key authentication, identity mismatch, request rejection, compound stages, containment, isolation, recovery and export cases |
| Rejected SSH requests | passed | Exec and subsystem unsupported; direct-TCP and remote forwarding denied; all four persisted with `accepted=false` |
| Compound stage evidence | passed | `missing \| echo recovered` retained stage statuses `[127, 0]` despite final status 0 |
| Rust dashboard | unchanged from verified predecessor; 4 locked tests and formatting passed | No Rust source changed in this candidate |
| No-cache image and inventory | passed | Current source/config image; 91 Debian and 26 Python packages recorded |
| Container/OS CVE scan | pending | No result is claimed because the available scanner requires unauthorized external metadata disclosure |

The injected PostgreSQL errors printed by the Linux harness are intentional outage and uncertain-commit stimuli. The harness passed only after durable retention, deduplication and export reconciliation succeeded.

## Gate map

| Gate | Current decision | Remaining work |
|---|---|---|
| G1 supported interaction | Partial, materially advanced | Reconcile every declared command/flag/effect row through real SSH; local reference and rejected-request paths pass |
| G2 isolation | Partial | Named cross-session, traversal, permission and restricted-worker cases pass; complete the frozen breadth matrix |
| G3 evidence | Partial, materially advanced | Stage results, request outcomes, forced worker interruption and named retry/crash cases pass; remaining lifecycle-boundary and transport-short-write cases stay open |
| G4 UI/export | Passed for the frozen synthetic procedure | Do not generalize to arbitrary scale |
| G5 deterministic/AI | Partial | Engineering treatment checks pass; blinded review is required only for an AI-realism improvement claim |
| G6 recovery/capacity | Partial | Supported 8-session fault envelope passes; soak and remaining exhaustion cases stay open |
| G7 release | Partial | Candidate, inventory and reproduction evidence exist; authorized container/OS CVE assessment remains open |

## Next work

1. Generate a contract-driven real-SSH matrix for every supported command row without pretending Mirage is GNU/POSIX compatible.
2. Complete the remaining G3 lifecycle/transport uncertainty points and G6 soak/exhaustion procedures.
3. Obtain an authorized local/offline container scan or explicit authorization for the external scanner's metadata disclosure.
4. Freeze a new dated candidate after any source, test or included-document change.
