# Verification and research protocol

Version 1.0 — 2026-09-25. Requirements: [MVP](RESEARCH_MVP.md). Work packages: [backlog](IMPLEMENTATION_BACKLOG.md).

Status reviewed 2026-10-12: G1–G7 passed for the October 11 frozen controlled-lab MVP, now recorded in implementation commit `fde3b98`. The [release index](RELEASE_EVIDENCE_INDEX_2026-10-11.md) contains the final decisions. Procedures and targets below remain the reference for future revalidation; unmeasured research metrics are not retroactively claimed as measured.

## Evidence levels

Source inspection establishes implemented paths, not runtime correctness. Unit tests establish their tested cases. Linux integration establishes the exercised deployment. Load tests establish only their hardware/workload envelope. Human studies establish only their sampled population and protocol. Keep these distinctions in every report.

## Current observations

After the 2026-10-11 lease-fencing regression, `PYTHONPATH=src pytest -q` outside the sandbox returned 244 passed and 7 skipped. The suite includes 107 named machine-readable command cases plus identity/30-handler coverage, parser/redirect fixtures, stage preservation and resource bounds, treatment isolation/provenance, stable session reference time, fault-injected mutation-journal/orphan-lifecycle recovery, bounded projection checkpointing, full-spool refusal before mutation, bundle identity/model-digest checks and non-empty deterministic artifact checks. The 7 legacy infrastructure skips are not passes. A restricted sandbox run returned Redis startup errors and cannot characterize code correctness.

`docker compose -f docker-compose.yml config --quiet` and the `--profile inference` graph both passed. The base service list excludes Ollama and resolves the core to deterministic mode. This validates configuration rendering, not fresh Linux startup or model preparation.

`cargo check --manifest-path src/chronos/dashboard/Cargo.toml` passed during the preceding review in this conversation. It proves compilation, not running UI behavior. These observations use the commit plus local modifications identified in the backlog. No full current Linux/UI/model release verification is claimed.

After B7/B10 and the eframe/egui 0.36.2 migration, `cargo test --manifest-path src/chronos/dashboard/Cargo.toml` returned 4 passed and `cargo check` passed. The automated PostgreSQL scale harness passed with 125 finalized sessions, 1,250 events, frozen-snapshot page sizes 50/50/25, concurrent-insert isolation until refresh and an older session's 10-event raw/redacted exports. A temporary macOS app bundle was then exercised against those disposable stores: 126 rows appeared over three pages, an explicit session link opened evidence-linked detail, analytics disclosed its 1,000-event preview cap, provenance displayed the scoped blob hash, stream pause/resume worked, both UI export modes completed, restart succeeded, and dependency offline/reconnect states were observed. The raw UI export contained the seeded secret while the redacted export did not. This passes G4 for the named synthetic procedure; it does not establish arbitrary-scale UI performance.

On 2026-10-05, `bash tests/integration/run_linux.sh` passed on Docker Engine 29.8.1 using uniquely named disposable resources. It exercised all 30 declared command handler names over contained SSH/FUSE and reconciled each to durable results/stages, including explicit malformed-descriptor rejection and `grep --` with a dash-prefixed pattern. It also covered password/public-key authentication, identity mismatch, exec/subsystem/direct-TCP/remote-forward rejection, compound stage export, isolation, deterministic generation, forced worker death, database outage retention, uncertain-commit deduplication and export correlation. The machine-readable matrix covers every documented command option/form plus representative benign, malformed and effect cases; the parser suite covers grammar, redirects and bounds. G1 therefore passes for the explicitly bounded v1 contract. Core/FUSE restart evidence is recorded in the G3 assessment; the remaining capacity soak is tracked separately under G6.

On 2026-10-08, the expanded Linux procedure passed bidirectional same-path file isolation, peer delete/list resistance, environment separation, absolute/relative traversal containment, absent runtime/procfs paths, protected-path mutation denial across write/create/mkdir/remove/copy/move, participant-path writes and peer survival after worker death. The separate restricted-worker process check and live `/proc` assertions verified chroot, UID/GID 1000, zero effective capabilities, no-new-privileges, seccomp filtering and denial of new sockets, fork, exec and privilege regain. G2 passes for this declared emulator/container boundary; trusted core/kernel/storage compromise, arbitrary code and malware containment are outside the claim. See [G2_ISOLATION_ASSESSMENT_2026-10-08.md](G2_ISOLATION_ASSESSMENT_2026-10-08.md).

G3 passes the declared evidence boundary. Deterministic fixtures and disposable Linux faults cover matching submission/result IDs, every pipeline stage, command-effect attribution, duplicate/uncertain database commits, outbox exit, state-commit/audit-admission failure, lifecycle recovery, real worker death and whole-core kill. Incomplete execution remains `unknown`; generated, locally accepted and remotely delivered bytes are not conflated. See [G3_EVIDENCE_ASSESSMENT_2026-10-08.md](G3_EVIDENCE_ASSESSMENT_2026-10-08.md).

G5 passes the operational criterion with deterministic artifacts as the release baseline. No-model startup, unavailable/invalid/slow/incomplete model behavior, prepared-bundle integrity, concurrent deduplication and participant-write fencing pass. The engineering comparison does not establish greater AI realism, and the MVP makes no such claim. See [G5_TREATMENT_ASSESSMENT_2026-10-08.md](G5_TREATMENT_ASSESSMENT_2026-10-08.md).

Earlier candidates are historical. The 2026-10-11 offline image assessment closes the scanner gap; the current release index records the source freeze, extracted-copy verification and G7 decision. A second host and bit-identical rebuild are stronger optional evidence, not mandatory criteria in this plan.

The disposable load harness subsequently passed a 32-session whole-core kill/restart with 32/32 durable `interrupted/orphaned_session` closes; an 8-session Redis stop/restart with 8/8 reconciled closes; and an 8-session, 45-second run containing a 30-second PostgreSQL outage with 1,378 submitted/audited commands, 8 finalized summaries, p50 52 ms, p95 138 ms and max 227 ms. A separate 32-session PostgreSQL-outage stress run timed out 7 clients while the SQLite backlog drained. The documented 32-connection ceiling is therefore saturation-only; no 32-session service level is claimed.

A 2026-09-27 dependency assessment found zero known vulnerabilities among 25 resolved Python packages and zero RustSec vulnerabilities, unsound advisories or yanked crates in the 502-package cross-platform dashboard lockfile. RustSec reports one informational unmaintained `ttf-parser` dependency in a non-macOS `ab_glyph` target path; the active macOS renderer resolves through `skrifa`. The 2026-10-11 Trivy image scan instead used a separately downloaded database and disabled networking during analysis. Its 164 Debian package/advisory matches and zero Python findings are retained with dispositions in [G7_RELEASE_ASSESSMENT_2026-10-11.md](G7_RELEASE_ASSESSMENT_2026-10-11.md).

A bounded live `llama3:8b` request produced a validator-accepted note in 6.22 seconds. A disposable-Redis end-to-end preparation then produced all six approved manifest artifacts using the installed `llama3:8b` and `llama3.2:3b` tags; one invalid Ubuntu output was rejected and retried. Bundle schema/integrity, generation-component invalidation and immutable model-digest provenance are regression tested. These checks establish the live path, not the 30-independent-trial comparative protocol below.

## Mandatory release gates

| Gate | Requirements | Procedure | Pass criterion |
|---|---|---|---|
| G1 Supported interaction | R1/R2/R5 | Reference fixtures for every supported syntax/flag, benign and malformed input, redirects and file effects | Zero unexplained contract mismatches; unsupported cases explicit |
| G2 Isolation | R3/R13 | Two concurrent sessions with distinct secrets/files; traversal, permissions and restricted-worker checks | Zero cross-session disclosure/mutation and no forbidden capability in tested boundary |
| G3 Evidence | R4–R7 | Known submissions/stages/effects; duplicates, retries and crash at each lifecycle boundary | Exact counts for known events; unresolved operations explicitly unknown; no inferred success |
| G4 UI/export | R8–R10/R14 | Over 100 sessions and 1,000 events; pause, reconnect, restart, old-session lookup; raw/redacted export | Selected evidence retrievable; raw counts reconcile; omissions disclosed; no fabricated expertise |
| G5 Deterministic/AI | R11/R12 | No-model fresh start; model unavailable/invalid/slow; concurrent prepared reads; participant writes | Core workflow works without inference; no invalid accepted required artifact in tests; no overwrite |
| G6 Recovery/capacity | R7/R13 | Disposable PostgreSQL/Redis outage, core kill, spool/storage full and restart | Durable admitted attempts retained or explicitly accounted for; no silent loss/admission without evidence |
| G7 Release | R15 | Frozen-source fresh install, running console walkthrough, dependency/image assessment | Reproducible setup and evidence; unresolved risks/limitations explicit |

Gates do not establish universal security or public-deployment safety. Record exact attack/fault cases, not merely gate names.

## Test execution discipline

Safe starting checks:

```bash
PYTHONPATH=src pytest -q --tb=short
cargo check --manifest-path src/chronos/dashboard/Cargo.toml
```

Tests require installed dependencies and a runnable local `redis-server`; default regressions use disposable Unix-socket Redis. Do not turn on `--legacy-infrastructure` casually: those tests can mutate external Redis or stop containers.

Review `tests/integration/run_linux.sh` before running. It builds a test image and owns named disposable containers/network; it requires Docker and Linux FUSE support and may leave its test image behind. Its current scope is not all G1–G7. Recovery/load scripts must be inspected for targets before use; never conduct exhaustion/outage tests against retained operator evidence.

Add meaningful regression cases for B1–B12, not tests that merely restate implementation. Test short transport writes, audit failure after a state effect, cache failure after summary progress, malformed events and replay. Exercise the actual UI; screenshot/build success alone is insufficient.

## Performance acceptance targets

The one-hour capacity run and bounded recovery results are measured in the [G6 assessment](G6_CAPACITY_ASSESSMENT_2026-10-11.md). Targets below are not blanket claims that every metric or workload has been measured; consult that assessment for actual measurements and limitations. Final release decisions and fresh-install evidence are in the [release index](RELEASE_EVIDENCE_INDEX_2026-10-11.md).

Freeze these before formal evaluation and version any revision. Initial target environment: documented Linux machine, core limited to 2 vCPU/2 GiB as in Compose, dependency resources reported separately, same local client/network, preloaded deterministic artifacts.

- At 1 and 8 simultaneous sessions, target p95 client-observed completion of a fixed small command workload at or below 1 second, with zero unexpected errors in at least 100 measured sequences per condition.
- Exercise the existing 32-connection ceiling as a stress condition, reporting saturation and degradation; do not claim 32-session service-level performance unless separately met.
- Run an initial 60-minute deterministic soak at 8 sessions; require no unexplained growth or evidence discrepancy. Longer operation is a post-MVP gate.
- Target p95 audit visibility within 5 seconds in the no-fault 8-session condition. Report outbox delay and summary delay separately.
- AI preparation is off the interaction path. Declare per-artifact budgets and measure them; lazy AI is experimental until its client-facing failure/latency behavior meets a separately frozen contract.

These are engineering targets chosen for this project, not published standards. If hardware cannot meet them, diagnose and either optimize or revise the supported envelope transparently before collecting final results. Do not change thresholds retrospectively to turn failures into passes.

## Research question and treatments

Primary question: does constrained, validated AI preparation improve artifact plausibility or consistency relative to a deterministic baseline, at what cost, and without degrading evidence correctness?

Treatments: A deterministic profile; B same profile with approved prepared AI artifacts. Keep emulator, profile facts, command set and infrastructure equal. Optional C is lazy generation, explicitly a separate latency treatment. Cowrie is an optional external baseline; pin its version/mode and report unmatched feature coverage rather than declaring universal superiority.

Use at least 30 independent preparation trials per required AI artifact for an initial engineering evaluation. This is a practical starting sample, not a statistical power calculation. Repeated cached reads are not independent generations. Record all failed/rejected/timeout/fallback trials; never select only successful outputs. Freeze prompts, policy, validator, model digest, seeds where supported and hardware. Repeatable input does not guarantee deterministic model output.

The 2026-09-27 valid-only engineering run completed this trial count: prepared AI accepted 172/180 after the two-attempt limit, while the corrected deterministic templates accepted 180/180. Timing boundaries were aligned in the harness and the deterministic treatment was rerun on 2026-09-28. Results and the original schema limitation are in [PREPARED_AI_EVALUATION_2026-09-27.md](PREPARED_AI_EVALUATION_2026-09-27.md). The run does not characterize the randomized production category distribution. The plausibility/contradiction comparison remains unscored because no independent blinded review was performed; the run must not be cited as evidence that AI is more realistic.

The current generation policy includes empty, broken and corrupted categories. Define a coherent evaluation profile: intentional degraded artifacts may be a separate labeled treatment, but cannot count as valid required configuration or be mixed silently into the primary comparison. A synthetic credential must never grant access to a real system. Preparation success alone does not establish semantic consistency.

Metrics: supported-command agreement, evidence reconciliation, contradiction count under a published rubric, accepted generation rate, rejection/fallback rate by artifact, preparation latency, cached read latency, client command latency, CPU/memory and audit lag. Report sample counts, errors, median/p95/p99 where sample sizes support them; small-sample p99 is effectively a maximum and must be labeled accordingly.

Store run ID, UTC interval, source revision/patch hash, image/dependency/model identifiers, profile/seed, cache state, workload, concurrency, instrument settings and raw results. Disclose instrumentation overhead. Avoid treating many commands from one session as independent people; analyses must respect session/run clustering.

## Optional human study

Only claim recognition/engagement results after actual authorized participants and required institutional procedures. Predefine tasks, allocation, recognition endpoint, observation period and reporting rubric. Record recognition with evidence and adjudication. Unrecognized sessions at study end are censored, not zero-second discoveries. Longer duration alone is not better deception. Do not infer a visitor's expertise from Mirage scores.

For stronger claims, use independent or blinded artifact review and report reviewer agreement. If only the maintainer assesses outputs, state that limitation. Do not manufacture participant data, statistical significance or attack coverage.

## Release evidence bundle

Include manifest of software/configuration hashes; test commands/results/skips; supported command contract; deployment diagram; vulnerability assessment date and disposition; load/raw measurements; sample raw/private and redacted exports; reproduction instructions; known limitations and gate decisions. Keep secrets out of shared bundles. Gate status starts pending until evidence exists.
