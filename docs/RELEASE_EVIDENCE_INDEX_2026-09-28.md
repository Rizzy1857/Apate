# Release evidence index — 2026-09-28

This index identifies the current Mirage Research MVP candidate and the evidence that can be attributed to it. It is not a declaration that every release gate has passed.

## Candidate identity

- Frozen bundle: `evidence/release_candidate_20260928/`
- Base commit: `a098fe02771802de03b9c64c8fbce52d82defc38`, plus the working-tree files captured in the archive and the recorded tracked patch
- Source archive: `source.tar.gz`, SHA-256 `6491e064cc2955a30f4d946c029e9f9fa7272d47f4630c2f0d0233047894e6d6`
- Source manifest: 158 files, SHA-256 `e786f7f9fe91e45f307fa0b4886d178376cf4d4e4772db31b24dde27f68ff5d5`
- Candidate record: `candidate.json`, SHA-256 `48f075beb3734acbc27de8c8ec408cb19206a25913475257771ec667e960cfdd`
- Completion record: `complete.json`, SHA-256 `3c08cb2fb5cb51602fecac48246f4a26aa756956ed3a0b14d7a96378d6974e19`
- No-cache image identity: `sha256:db8c0841a6e3f48263c31e87870e4a076f64c3681edf506ca6bf1136470d6ba0`
- Resolved inventory: 91 Debian packages and 26 Python distributions in `image_inventory.json`, SHA-256 `97323eaeeaf69d8c913ffbe174069c895d8825166eb3258b68b9209ad99748a9`

The archive excludes generated evidence, caches, Rust build output, bytecode and `.DS_Store`. Every member is individually hashed. The archive and manifest were independently reconciled after creation.

## Candidate verification record

| Check | Result | Scope |
|---|---|---|
| Extracted Python suite | 132 passed, 7 skipped | All default tests; skipped legacy infrastructure cases are not passes |
| Extracted Rust dashboard | formatting passed; 4 tests passed; locked check passed | Compilation and unit behavior, not a replacement for UI interaction |
| Build from extracted archive | passed | Reused identical cached layers from the prior no-cache build; image config and platform manifest matched |
| Current Linux/FUSE harness | passed | Named containment, isolation, fault, evidence and export cases |
| Native console walkthrough | G4 frozen procedure passed | Synthetic 126-session/1,250-event dataset and named reconnect/export actions |
| Dependency audits | Python and Rust known-vulnerability audits passed | Dates, package counts and one informational Rust warning are in `STATUS.md` |
| Container/OS CVE scan | pending | No result is claimed because the available scanner required unauthorized external metadata disclosure |

The first sandboxed extracted-suite attempt could not start its temporary Redis processes and produced 34 fixture errors. The identical elevated run passed 101 tests; the failed attempt is environmental evidence, not silently reclassified as a code pass.

## Requirement and gate map

| Area | Current evidence | Decision |
|---|---|---|
| R1–R2 supported shell contract | versioned contract, 31-case reference file, parser/redirect/outcome regressions and Linux subset | Partial: full real-SSH row/stage reconciliation remains open |
| R3 isolation | Linux restricted-worker, SSH/FUSE and cross-session cases | Partial: exercised cases passed; gate breadth remains as defined in G2 |
| R4–R7 evidence/lifecycle | stable IDs, outbox, mutation journal, crash/retry and export reconciliation tests | Partial: named cases passed; full lifecycle fault matrix remains open |
| R8–R10, R14 console/export | scale harness plus native walkthrough | G4 passed for the frozen procedure |
| R11–R12 deterministic/prepared AI | explicit treatment, no-model, validator, provenance and 180-trial engineering runs | Partial: engineering behavior passed; blinded plausibility review is required only for an AI-improvement claim |
| R13 capacity/recovery | 8-session supported envelope passed; 32-session stress boundary disclosed | Partial: soak and remaining exhaustion cases are open |
| R15 release | frozen candidate, manifests, resolved inventory, extracted tests/build and operator documentation | Partial: authorized container/OS CVE assessment remains open |

Therefore G4 is passed. G1–G3 and G5–G7 remain partial under the definitions in [VERIFICATION_PLAN.md](VERIFICATION_PLAN.md). Passing individual checks must not be generalized into universal attack coverage, public-deployment safety or proof that AI artifacts are more realistic.

## Remaining release work

1. Run an authorized local/offline container scanner, or explicitly authorize the metadata disclosure required by Docker Scout. Record database timestamp, severities, fixes and dispositions.
2. Complete the still-open G1–G3, G5 and G6 procedures rather than inferring them from current regression coverage.
3. If claiming AI realism improvement, perform the frozen independent/blinded plausibility and contradiction review. Otherwise retain the narrower engineering claim.
4. Re-freeze the candidate whenever source, tests or operator documents change; the hashes above describe only this bundle.
