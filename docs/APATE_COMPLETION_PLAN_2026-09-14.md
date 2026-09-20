# Apate completion plan: red-team research MVP

Date: 2026-09-14. Status: proposed implementation baseline, not a completion claim.

## Revised objective

Finish Apate as a contained SSH deception environment for authorized red-team research: reliable and coherent AI-backed artifacts, accurately attributed and measured visitor actions, and a Rust desktop UI for live observation, historical evidence retrieval, and reproducible report export. Keep simulated activity, operational diagnostics, measured facts, and AI interpretations distinct.

This replaces the vague working scope of “do 1 to 4” in this report. The app's existing goal remains usage-limited; its objective/status could not be edited or resumed using the available goal controls.

## Scope and definition of finished

Target a research MVP, not a full Linux VM, arbitrary malware sandbox, or a production-safe public deployment. Unsupported commands remain blocked. No public exposure is implied by this plan. Preserve existing data and user changes. Use disposable stacks for disruptive tests.

Completion requires evidence for each gate below, with reproducible commands, build/configuration identifiers, and explicit limitations. A passing unit suite alone is insufficient. Human discovery-time results require actual authorized participants; they cannot be manufactured by software tests.

## Current findings

- Local SSH, session isolation, persistent auditing, and native Ollama connectivity have been exercised. Historical tests do not automatically validate later changes.
- AI generates selected manifest files, not arbitrary terminal responses. Reliability, TLS artifact validity, and absolute generation deadlines remain unresolved.
- World simulation is experimental and not running locally. The terminal entropy helper returns mostly constants rather than consuming the plugin's Redis state.
- Commands are audited before execution. The evidence collector incorrectly treats submission as a successful interaction and accumulates heuristic confidence on repetition.
- The Rust UI uses hard-coded database connection settings. Its audit query selects the newest 50 rows and advances its cursor to the maximum ID, allowing older unseen rows in a burst to be skipped. Paused display updates are discarded; the live list is capped at 1,000 entries. These are viewer completeness problems, not proof that database records were deleted.

## Phase 1 — Measurement and evidence contract

Define a versioned event schema before adding dashboards or inference-based analysis.

Each command receives a session ID, command ID, sequence number, and submitted/start/completion events. Record working directory, outcome, exit status when available, affected paths, bytes actually read/written, and bounded response evidence. Link filesystem events to their initiating command. Treat blocked, denied, unsupported, timed-out, and completed operations separately. A crash leaves an explicit unknown/interrupted outcome, never inferred success.

Use UTC timestamps for correlation and monotonic durations for timing within one process. Record server processing and client-observed latency separately. Include run ID, software revision, profile, model digest, settings, concurrency, and instrumentation configuration in research exports.

Label origins explicitly: participant, scripted test, synthetic world activity, and operational diagnostics. Preserve original command evidence under access controls; provide redacted exports because commands may contain secrets. Continue omitting authentication passwords. Define retention, capacity alarms, and overflow/fail-closed behavior rather than silently losing records.

Gate: scripted ground-truth sessions reconcile submitted commands, outcomes, and file effects exactly, including denied operations, retries, crashes, and replay. Report missing outcomes and measurement gaps explicitly. Source-address attribution must distinguish trusted relay information from an unverified claimed address.

## Phase 2 — Rust UI as the primary research console

Keep storage collection independent of the UI: closing or pausing the UI must not stop capture. Use a configurable, least-privilege read path to authoritative evidence without publicly exposing PostgreSQL or Redis.

Repair ascending cursor pagination, reconnect behavior, duplicate handling, and history retrieval. Do not assume allocation-order database IDs alone prove transaction commit order; test concurrent commits and replay reconciliation. Pause freezes presentation, not acquisition or historical access. The 1,000-row live cache must not limit exports.

Provide live sessions, command/outcome timelines, linked file activity, experiment filters, measured latency distributions, AI provenance, and collection health. Show queue backlog, last successful synchronization, truncation, incomplete sessions, and disconnected state. Separate measured facts from rule labels.

Export complete selected runs as versioned JSON/CSV plus a readable Markdown report with event references, counts, configuration, and artifact hashes. Hashes support integrity checking; do not claim tamper-proof custody without additional controls.

Gate: a burst exceeding the current page size and live-cache limit remains fully retrievable and exportable after pause, restart, and reconnection. Exported records reconcile against authoritative storage. Verify the running UI, not only compilation.

## Phase 3 — Reliable AI artifacts

Maintain deterministic identity-critical files and restrict AI to approved manifest artifacts. Repair valid matching synthetic certificate/key content and configuration consistency. Establish tested end-to-end generation budgets including connection, headers, streaming stalls, cancellation, retries, and lease expiry.

Evaluate every AI-backed path across repeated cold/warm and concurrent runs. Track accepted generation, rejection, timeout, fallback, bytes, latency, and model/configuration provenance per path. Require tests for every fallback and for protection against overwriting participant changes. Replace the weak “any AI success” criterion with per-artifact results and explicit release thresholds chosen before final evaluation.

Prefer validated pre-generation of suitable baseline artifacts before admitting research sessions, with session-isolated content and bounded fallback for lazy reads. Record cache/preparation conditions because they materially change measured latency. Do not hide fallback as AI success.

Gate: all required artifact checks pass; repeated evaluation meets declared availability and latency targets; no unbounded generation or invalid accepted critical configuration. Connectivity alone does not satisfy this gate.

## Phase 4 — Coherent world simulation

Integrate a small seeded world model only after evidence attribution works. Reconcile profile identity, uptime, resource values, process snapshots, logs, and file metadata. Choose explicit baseline/session ownership; background events must not overwrite participant changes or leak session state.

Connect entropy consumers deliberately. Update actual content and metadata consistently instead of inventing file sizes. Persist the seed, simulated clock, and world events for replay. Synthetic activity is visible in a separate UI lane and excluded from participant metrics by default.

Gate: repeated seeded tests reproduce world evolution, command outputs remain mutually consistent, and synthetic activity cannot increase participant-action counts or risk confidence. Unintegrated plugins stay disabled and documented as experimental.

## Phase 5 — Reports and optional AI summaries

Generate the factual report deterministically first: experiment setup, session timeline, outcomes, file effects, timings, completeness, and limitations. Replace probability-like heuristic confidence with clearly named rule matches unless calibration data supports a probabilistic score.

Optionally summarize completed sessions locally using structured evidence. Every substantive summary claim must cite event IDs; mark interpretations and uncertainty. Treat commands and file contents as untrusted data, never instructions. Give the summarizer no execution tools or external sending capability. Bound input/output and record coverage, omitted events, model, prompt version, and generation time. An AI failure must not block collection or factual reports. Isolate summarization workload from live artifact generation and record its benchmark impact.

Gate: a labeled evaluation set measures unsupported claims, missed important actions, citation correctness, and prompt-injection resistance. AI cannot invent outcomes, determine attacker identity, or independently establish discovery time.

## Phase 6 — Research validation and release

Run end-to-end SSH/FUSE/UI/export tests, regression suites, dependency/image scans, sustained load, storage exhaustion, and database/Redis/core failure recovery. Benchmark single-session and concurrent workloads against a controlled real SSH host using the same client/network and defined command workloads. Report sample counts, p50/p95/p99, errors, cold/warm state, and environmental differences; do not equate a local smoke test with WAN latency.

For discovery time, define the endpoint before collecting data: time from an agreed session start to a participant's recorded recognition of deception, with corroborating evidence and reviewer adjudication. Participants who never identify it are censored observations, not zero-second discoveries. Report censored counts and an appropriate time-to-event analysis rather than a misleading mean among discoverers. This is distinct from Apate flagging a suspicious command. No current human MTTD is established.

Release deliverables: working Rust research console; versioned evidence schema; reliable artifact pipeline; coherent enabled world subset; reproducible evaluation results; example redacted research export; accurate operator documentation and explicit remaining risks. Software readiness can be demonstrated with scripted tests; human research conclusions remain pending participant study.
