# Release evidence index — 2026-10-08 G2

Historical candidate, superseded by the [2026-10-11 release index](RELEASE_EVIDENCE_INDEX_2026-10-11.md). The decisions below describe this earlier candidate only, before subsequent verification closed the remaining gates.

## Candidate identity

- Frozen bundle: `evidence/release_candidate_20261008_g2/`
- Base commit: `a098fe02771802de03b9c64c8fbce52d82defc38`, plus archived working-tree files and the recorded tracked patch
- Source archive: SHA-256 `c72ec41b1271099c38da65e99503d4cd892ec7a0155c5cb20515c48745d6cee7`
- Source manifest: 161 files, SHA-256 `cf1af8dbb9e25ffa02b039e7f6ac7b46c7870dc143fca9072dbe6bb4617fa2df`
- Candidate record: SHA-256 `5f6cce710aa9d5f3ac416afcb0c8b833509711e61172ef1907f7861ec965fc17`
- Completion record: SHA-256 `162386c3baa536aacd9aab7a12d95fb3407cb7d3e0816afeecfa29c4e47f4d2b`
- Tracked patch: SHA-256 `1cafa326b6ff1c1fc09d790125eae45f4283c6870fdf87c7c7dbfd1a4b34519a`
- No-cache image identity: `sha256:2bf56d3ba8b77366c1462d48bb3e739b93c28bc44411c559562bb9b979cfc9a6`
- Resolved inventory: 91 Debian packages and 26 Python distributions; SHA-256 `af9a74867888827dd6059a49d96c17981b090cc8c0c26456f5f34ea448f2fac4`

Evidence indexes are excluded from their own archives to avoid self-referential hashes. Generated evidence, caches, Rust build output, bytecode and `.DS_Store` are also excluded. Every archived member is individually hashed.

## Verification record

| Check | Result | Scope |
|---|---|---|
| Python suite, working tree | 242 passed, 7 skipped | Default suite with normal local Redis permissions; legacy infrastructure skips are not passes |
| Python suite, extracted archive | 242 passed, 7 skipped | Exact `source.tar.gz` contents in a clean temporary directory |
| G1 command contract | passed | 107-case matrix, parser/redirect fixtures and all 30 handlers through real SSH/FUSE |
| G2 two-session namespace | passed | Same-path distinct secrets, bidirectional non-disclosure, peer deletion/list resistance and environment separation |
| G2 traversal/permissions | passed | Absolute/relative traversal containment; runtime/procfs absent; protected write/create/mkdir/remove/copy/move denied |
| G2 worker containment | passed | Chroot, UID/GID 1000, zero effective capabilities, no-new-privileges, seccomp; socket/fork/exec/setuid denied |
| G2 failure isolation | passed | Forced death closed one session; the peer remained functional |
| Archive manifest | passed | 161/161 members, byte counts and SHA-256 values reconciled |
| Rust dashboard | unchanged from verified predecessor | Five archived dashboard files are byte-identical; four locked tests and formatting previously passed |
| Container/OS CVE scan | pending | No result is claimed because the available scanner requires unauthorized external metadata disclosure |

The PostgreSQL errors printed during the Linux harness are deliberate outage and uncertain-commit stimuli. The harness succeeds only after retained evidence drains and reconciles.

## Gate decisions

- G1: passed for the explicitly bounded v1 command contract. This is not Bash, GNU coreutils or POSIX compatibility.
- G2: passed for the declared emulator/Linux-container boundary. Trusted infrastructure compromise, arbitrary code and malware containment are outside the claim.
- G3: partial. Stage evidence, request outcomes, forced worker interruption and named retry/crash cases pass; remaining lifecycle boundaries and real transport short-write uncertainty stay open.
- G4: passed for the frozen synthetic UI/export procedure.
- G5: partial; engineering treatment behavior passes, with no AI-superiority claim.
- G6: partial; the supported fault envelope passes, while soak and remaining exhaustion cases stay open.
- G7: partial solely because an authorized container/OS vulnerability result is missing. Bit-identical rebuilds and a second host remain optional stronger evidence.

## Next work

1. Finish G3 lifecycle-boundary and real transport short-write/disconnect reconciliation.
2. Finish G6 soak and remaining exhaustion procedures.
3. Obtain an authorized local/offline container scan or explicit authorization for the external scanner's metadata disclosure.
