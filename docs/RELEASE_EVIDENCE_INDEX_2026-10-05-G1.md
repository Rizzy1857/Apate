# Release evidence index — 2026-10-05 G1

This is the current Mirage Research MVP candidate after closing the bounded v1 supported-interaction gate. Earlier dated bundles remain historical evidence. This index does not declare every mandatory gate passed.

## Candidate identity

- Frozen bundle: `evidence/release_candidate_20261005_g1/`
- Base commit: `a098fe02771802de03b9c64c8fbce52d82defc38`, plus archived working-tree files and the recorded tracked patch
- Source archive: SHA-256 `63c278343dba6476ffae005f52cc3f1cd8b82b0e1e153ccad0805730c0c79690`
- Source manifest: 160 files, SHA-256 `7b119d20f564055ae5c16cb1d760977ffc7608e63e9844fc4b834e98c17898c4`
- Candidate record: SHA-256 `f7eaccc1c6acdac2780e55ab3e1258f5f71c941868a1a106df74f1fbf21862a7`
- Completion record: SHA-256 `8dab9d1475c60cf75cffd88503082650354b885be3f5dbc6ec9daa4e73140dbb`
- Tracked patch: SHA-256 `b65e242930ac5ad226ed1aaf86ea62c909024e08184748108cdc94308fb1effd`
- No-cache image identity: `sha256:294372516a6247233fc01895b164cfc045096ee0552aee90efce5bfcb25670ba`
- Resolved inventory: 91 Debian packages and 26 Python distributions; SHA-256 `c6e879a3bda810f5bc3e3a38bf7875b724faa3b4fa3bb9a3dff5dfd01a70c7bd`

Evidence indexes are excluded from their own archives to avoid self-referential hashes. Generated evidence, caches, Rust build output, bytecode and `.DS_Store` are also excluded. Every archived member is individually hashed.

## Verification record

| Check | Result | Scope |
|---|---|---|
| Python suite, working tree | 242 passed, 7 skipped | Default suite with normal local Redis permissions; legacy infrastructure skips are not passes |
| Python suite, extracted archive | 242 passed, 7 skipped | Exact `source.tar.gz` contents in a clean temporary directory |
| Machine command matrix | 108 passed | 107 named cases plus identity/unique-ID/30-handler coverage |
| Parser/redirect contract | 32 passed | Grammar, malformed input, redirects, effects, limits, traversal and stage semantics |
| Linux SSH/FUSE integration | passed | All 30 handlers, `grep --`, parser failure, requests, identity, isolation, recovery and export cases |
| Archive manifest | passed | 160/160 members, byte counts and SHA-256 values reconciled |
| Rust dashboard | unchanged from verified predecessor | Five archived dashboard files are byte-identical; four locked tests and formatting previously passed |
| Container/OS CVE scan | pending | No result is claimed because the available scanner requires unauthorized external metadata disclosure |

The PostgreSQL errors printed during the Linux harness are deliberate outage and uncertain-commit stimuli. The harness succeeds only after retained evidence drains and reconciles.

## Gate decisions

- G1: passed for the explicitly bounded v1 command contract. This is not Bash, GNU coreutils or POSIX compatibility.
- G2: partial. Named isolation/containment cases pass; the frozen breadth matrix still needs a final decision record.
- G3: partial. Stage evidence, request outcomes, forced worker interruption and named retry/crash cases pass; remaining lifecycle boundaries and real transport short-write uncertainty stay open.
- G4: passed for the frozen synthetic UI/export procedure.
- G5: partial; engineering treatment behavior passes, with no AI-superiority claim.
- G6: partial; the supported fault envelope passes, while soak and remaining exhaustion cases stay open.
- G7: partial solely because an authorized container/OS vulnerability result is missing. Bit-identical rebuilds and a second host remain optional stronger evidence.

## Next work

1. Close or explicitly disposition the remaining G2 isolation breadth cases.
2. Finish G3 lifecycle/transport uncertainty and G6 soak/exhaustion procedures.
3. Obtain an authorized local/offline container scan or explicit authorization for the external scanner's metadata disclosure.
