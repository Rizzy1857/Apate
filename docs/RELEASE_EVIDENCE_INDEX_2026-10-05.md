# Release evidence index — 2026-10-05

This is the current Mirage Research MVP candidate after the complete declared-handler SSH matrix. Earlier dated bundles remain historical evidence. This index does not declare every mandatory gate passed.

## Candidate identity

- Frozen bundle: `evidence/release_candidate_20261005/`
- Base commit: `a098fe02771802de03b9c64c8fbce52d82defc38`, plus archived working-tree files and the recorded tracked patch
- Source archive: SHA-256 `9d539917a59f5cc41df9b6abf964445f6db757787e1891c98103923874958871`
- Source manifest: 158 files, SHA-256 `2a76c78d521d9ee0eee11a22042db41013345cf3e22cb1813de9ce6e9c52181e`
- Candidate record: SHA-256 `9856a2f69beb00fcd6ab9e635bdc41aff267eb12a255ac121957c7df25aeee1e`
- Completion record: SHA-256 `a24ccbd5d70363344a85f35e10c31068251fb069ab5adeefa81bb1b134558075`
- No-cache image identity: `sha256:2d4f895e5646b43d88d0730f472f7823fb14ee16a6900adac9f50a514dd8e331`
- Resolved inventory: 91 Debian packages and 26 Python distributions; SHA-256 `50f908fd0468c379127b7f075a05c3f270b63f10d402361aebd01c0c81ea8e92`

Evidence indexes are excluded from their own archives to avoid self-referential hashes. Generated evidence, caches, Rust build output, bytecode and `.DS_Store` are also excluded. Every archived member is individually hashed.

## Verification record

| Check | Result | Scope |
|---|---|---|
| Python suite | 134 passed, 7 skipped | Default suite; legacy infrastructure skips are not passes |
| Declared-handler matrix | passed | All 30 registry names executed through a contained real SSH/FUSE session and reconciled to durable results/stages |
| Parser boundary | passed | Descriptor duplication returned an explicit parser failure over SSH, not a generic I/O error |
| SSH requests and identity | passed | Password/public-key, mismatch provenance, exec/subsystem/direct/remote forwarding rejection |
| Compound stages | passed | Earlier stage failure retained despite a zero final pipeline status |
| Isolation/recovery/export | passed for named harness cases | Cross-session secret, permissions, worker death, database outage, deduplication and raw export reconciliation |
| Rust dashboard | unchanged from verified predecessor | Four locked tests and formatting previously passed; source tree is byte-identical |
| Container/OS CVE scan | pending | No result is claimed because the available scanner requires unauthorized external metadata disclosure |

The PostgreSQL errors printed during the harness are deliberate outage and uncertain-commit stimuli. The harness succeeds only after retained evidence drains and reconciles.

## Gate decisions

- G1: partial, close to closure. Every command handler and major grammar/request path is now integrated, but all documented option/error combinations are not yet exhaustively reconciled.
- G2: partial. Named isolation/containment cases pass; the frozen breadth matrix still needs a final decision record.
- G3: partial. Stage evidence, request outcomes, forced worker interruption and named retry/crash cases pass; remaining lifecycle boundaries and real transport short-write uncertainty stay open.
- G4: passed for the frozen synthetic UI/export procedure.
- G5: partial; engineering treatment behavior passes, with no AI-superiority claim.
- G6: partial; the supported fault envelope passes, while soak and remaining exhaustion cases stay open.
- G7: partial solely because an authorized container/OS vulnerability result is missing. Bit-identical rebuilds and a second host remain optional stronger evidence.

## Next work

1. Convert the documented per-command option/error table into an exhaustive machine-readable fixture set and reconcile it over real SSH where behavior differs from the local dispatcher.
2. Finish G3 lifecycle/transport uncertainty and G6 soak/exhaustion procedures.
3. Obtain an authorized local/offline container scan or explicit authorization for the external scanner's metadata disclosure.
