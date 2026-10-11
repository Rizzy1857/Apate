# Beyond Mirage Research MVP

Version 1.0 — 2026-09-25. Future design, not implemented capability. [MVP](RESEARCH_MVP.md) remains frozen unless explicitly revised.

## Expansion order

| Stage | Benefit | Entry gate | Exit evidence |
|---|---|---|---|
| F1 Research usability | Multi-run comparisons, richer search and reproducible experiment presets | G1–G7 pass | Repeat a comparison from exported configuration; history remains complete |
| F2 Broader SSH observation | Supported exec mode, request-level telemetry and bounded upload quarantine | Stable lifecycle/effect schema | Per-request contracts, untrusted-file handling and storage tests |
| F3 Additional decoy protocols | HTTP or another selected protocol for a defined research question | Protocol-specific threat model and event mapping | Separate coverage and cross-protocol correlation tests |
| F4 Distributed sensors | Multiple controlled deployments contribute evidence | Authenticated ingestion, schema compatibility and tenancy design | Replay/tamper/rate-limit/isolation tests; provenance preserved |
| F5 Assisted interpretation | Optional local evidence-cited summaries | Reliable factual reports and labeled evaluation | Unsupported-claim/citation/injection metrics within predeclared bounds |
| F6 Field research | Longer deployment and real-world observation | Operations owner, retention, incident handling and reviewed exposure boundary | Field reliability and appropriately qualified findings |

Mirage Home branches from the shared schema and ingestion capabilities when its own gates pass; it is not merely the research Compose stack shipped to households.

## Keep a measurable contribution

Candidate research contributions include consistency constraints across generated files, recoverable evidence under faults, and the tradeoff between prepared and lazy generation. Evaluate each against the deterministic baseline and relevant existing systems. Cowrie already documents shell/proxy and experimental LLM operation; claims of novelty require a current literature review and precise comparison.

## Architecture decisions to revisit

**FUSE:** measure callback overhead, Linux privilege requirements, semantic bugs and test complexity. Prototype a direct virtual-filesystem backend only behind a stable interface. Compare the same contract and evidence output before migration. Do not run two authoritative state models indefinitely.

**World simulation:** extend only when a consistency experiment requires it. One seeded clock/resource model should govern related outputs. Preserve participant writes; keep synthetic origin and replay configuration. Legacy independent plugins must not mutate global state that conflicts with session state.

**Storage:** retain distinct state/outbox/evidence responsibilities until measurements justify simplification. Introduce indexing, pagination and incremental projections before distributed databases. Define backup restoration and retention testing before scale claims.

The 2026-10-11 soak also exposes substantial cumulative internal network traffic as histories grow. Prioritize measuring and reducing full-summary cache serialization and checkpoint payloads before increasing concurrency or adapting the collector for Home. Preserve raw-event replay and snapshot correctness when introducing incremental projections; a smaller payload must not silently omit evidence.

**AI:** one evaluated model is enough initially. Additional providers require independent transport/privacy/reliability evaluation. AI summaries must cite events, distinguish interpretations, report input coverage and have no execution/sending tools. Model failure must not interrupt collection.

**Higher interaction:** a real backend VM is a new execution and containment architecture. Treat malware capture, detonation, outbound access and reset policy as a separate project gate. The strict emulator cannot simply be loosened into arbitrary execution.

## Distributed research contract

Use authenticated sensor identity, unique event IDs, sensor sequence, schema versions, acknowledgements and idempotent retry. Keep origin, deployment type, rule/model version and collection mode. Quarantine invalid or conflicting events; rate-limit each sensor. Signed/authenticated submissions establish their sender, not the truth of attacker-controlled payloads.

Separate tenants and access controls. Data from volunteer household sensors is a biased sample shaped by deployment, uptime, selection and redaction; do not estimate population attack prevalence from it without an appropriate sampling design. No automatic feedback from research interpretations into blocking household devices.

## Stop conditions

Defer a feature when it lacks a testable benefit, introduces unbounded operational ownership, or prevents reproducing prior results. Do not add a second interface, protocol or model solely to make the project appear larger. Every extension needs a requirement, owner, maintenance cost and acceptance evidence.
