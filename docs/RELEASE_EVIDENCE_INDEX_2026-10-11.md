# Release evidence index — 2026-10-11

**Decision: G1–G7 pass for the bounded, local Mirage Research MVP.** This completes the documented college-project MVP, not Mirage Home or a public-production security product. The requirement and interpretation boundaries in [RESEARCH_MVP.md](RESEARCH_MVP.md) remain authoritative.

## Frozen deliverable

- [Source archive](../evidence/release_candidate_20261011/source.tar.gz): 167 files; SHA-256 `262284b8e360df9b206b51c74654dea74d0166eb9f12a12c12e82233582bdfbe`.
- [Manifest](../evidence/release_candidate_20261011/source_manifest.json): SHA-256 `756f3d3cf668f605e6364751d407bdb8b0594700c3253dab5f3c35d405467afa`.
- [Candidate identity](../evidence/release_candidate_20261011/candidate.json), [completion marker](../evidence/release_candidate_20261011/complete.json), [image/package inventory](../evidence/release_candidate_20261011/image_inventory.json) and [verification record](../evidence/release_checks_20261011/verification.json).
- Freeze base commit: `a098fe02771802de03b9c64c8fbce52d82defc38` **plus the archived working tree**, including then-untracked implementation files. That base commit alone is not this release. The final publication commit is identified by the Git history entry `Finalize Mirage Research MVP and verified release evidence`; the archive preserves its original pre-publication provenance.
- Soak-tested image: `apate-release:20261011`, identity `sha256:37aedd15dbea3605ee60ca5a4e40e7ecf1e201472c114483a8bf02cb7ac314ee`.
- Fresh extracted-source build: `apate-release-repro:20261011`, identity `sha256:d845b13704bd3112ca6698285185e2f50288e58e8ce9631e935449738dbe8892`. All 64 application/config files, 91 Debian package versions and 26 Python distribution versions match the tested image. Images are not bit-identical; future dependency resolution may change.

The archive excludes generated evidence and release indexes to avoid self-reference. Retain this index and its linked evidence alongside it; the source archive alone is not the complete evidence bundle. All archive members, sizes and hashes were verified after extraction and against the final working tree. Runtime and workload-harness hashes match the one-hour run; only the packaging helper changed among that run's recorded source inputs.

## Gate decisions and evidence

| Gate | Decision and bounded evidence |
|---|---|
| G1 — supported interaction | Pass: versioned 107-case command matrix, parser/redirect cases and all 30 registered handlers through SSH/FUSE; not Bash/GNU/POSIX compatibility. |
| G2 — isolation | Pass: concurrent namespace, traversal, permissions and restricted-worker cases in the [isolation assessment](G2_ISOLATION_ASSESSMENT_2026-10-08.md), rerun from extracted source. |
| G3 — evidence | Pass: named submission/stage/effect, short-write, retry and lifecycle boundaries in the [evidence assessment](G3_EVIDENCE_ASSESSMENT_2026-10-08.md). Uncertain operations remain unknown; simultaneous store loss is excluded. |
| G4 — console/export | Pass for the prior native 126-session/1,250-event procedure described in the [verification plan](VERIFICATION_PLAN.md). [All five dashboard files match that predecessor](../evidence/release_checks_20261011/dashboard_comparison.json); [four locked Rust tests pass](../evidence/release_checks_20261011/rust.log). |
| G5 — deterministic/prepared AI | Pass for the [operational treatment criterion](G5_TREATMENT_ASSESSMENT_2026-10-08.md); deterministic mode remains the release baseline. No AI-superiority claim. |
| G6 — recovery/capacity | Pass for the [eight-client envelope](G6_CAPACITY_ASSESSMENT_2026-10-11.md): full hour, 7,055 matching submissions/results/projected commands, 16 finalized sessions and no stale namespaces; named core/Redis/PostgreSQL faults reconciled. |
| G7 — release | Pass: clean extracted-source tests, no-cache fresh install, applicable native walkthrough and [offline vulnerability assessment with explicit residual risks](G7_RELEASE_ASSESSMENT_2026-10-11.md). |

Final extracted-copy checks: [244 Python passes, 7 explicit skips](../evidence/release_checks_20261011/extracted-python.log); [Linux/FUSE integration passed](../evidence/release_checks_20261011/extracted-linux.log); [fresh build passed](../evidence/release_checks_20261011/fresh-build.log). PostgreSQL failure messages in the integration log are deliberate fault stimuli, followed by recovery assertions. Skips are not passes. No test containers remain running.

## Reproduction and examples

Verify the archive SHA-256, extract into a new directory, and follow [HOW_TO.md](HOW_TO.md) for prerequisites and safe local operation. The release checks used `PYTHONPATH=src pytest -q`, `docker build --no-cache`, and `bash tests/integration/run_linux.sh` from that extracted directory. Docker/FUSE and a local Redis executable are required by the respective checks; use only disposable test resources. The exact hour-long workload, environment, rotations and raw evidence are linked in the G6 assessment.

Retained [raw example](../evidence/release_checks_20261011/example-raw/report.md) and [redacted example](../evidence/release_checks_20261011/example-redacted/report.md) were generated by the frozen exporter using [explicitly synthetic input](../evidence/release_checks_20261011/make_examples.py). Their completion markers hash all output files; sentinel removal was checked. They are format demonstrations, not captured attackers or additional runtime measurements.

## Residual risks and next phase

The final image scan reports 164 Debian package/advisory pairs, including 44 high matches across eight identifiers, and zero Python-distribution findings. No fixed Debian version was listed in the scan database. These findings are disclosed, not suppressed or declared harmless. Restrict use to the documented controlled lab and reassess dependencies before another deployment.

The soak measured p95 client latency of 139 ms and median core-memory growth of 41.95 MiB, below the predeclared 128 MiB limit. It also reported about 45 GB of internal core outbound traffic. Incremental evidence projection is a priority before scaling; multi-day reliability and separate p95 audit/summary visibility remain unmeasured. The 32-client outage stress case is a documented saturation failure, not supported service-level capacity.

Post-MVP research work is separated in [RESEARCH_FUTURE.md](RESEARCH_FUTURE.md); the future household product is specified in [MIRAGE_HOME.md](MIRAGE_HOME.md). Public exposure, arbitrary execution, malware detonation, universal attack capture and real attacker identity/expertise inference remain excluded. Any source/config change requires a new freeze and proportionate revalidation.
