# Mirage product and engineering plan

Version 1.0 planning baseline; status reviewed 2026-10-12. Maintainer: project owner, assisted by Codex. The controlled-lab Research MVP has passed G1–G7; see the [final release evidence](RELEASE_EVIDENCE_INDEX_2026-10-11.md) and [current publication status](STATUS.md). Further research and Mirage Home are separate post-MVP scopes. An AI assistant does not replace independent evaluation or human research participants.

## Reading order

The October 16 integrated Research extension is tracked by the
[requirements audit](INTEGRATED_ACCEPTANCE_AUDIT_2026-10-16.md) and
[October 16 release index](RELEASE_EVIDENCE_INDEX_2026-10-16.md). Current private-staging
acceptance is in the [October 19 release index](RELEASE_EVIDENCE_INDEX_2026-10-19.md),
with [October 22 success/failure checks](WORKING_REVIEW_2026-10-22.md) and the
[step-by-step operator guide](HOW_TO.md). The October 11
gate verdict above remains historical; it does not certify later changes.

1. [Research MVP specification](RESEARCH_MVP.md): product boundary and requirements.
2. [Architecture and evidence contract](RESEARCH_ARCHITECTURE.md): current implementation and required behavior.
3. [Implementation backlog](IMPLEMENTATION_BACKLOG.md): source audit, dependencies and scope reduction.
4. [Verification and research protocol](VERIFICATION_PLAN.md): release gates and defensible measurements.
5. [Beyond the research MVP](RESEARCH_FUTURE.md): gated extensions.
6. [Mirage Home](MIRAGE_HOME.md): separate future product and research contribution design.
7. [Current status](STATUS.md): dated implementation evidence.

## Authority

This set supersedes the older two-phase/six-month framing. Requirements describe intended behavior unless labeled implemented or observed. Source and dated tests establish implementation status; acceptance gates establish release status. The September 9 hardening review and September 10 handoff remain historical evidence. The retired September 14 plan and old roadmap are represented by short archival notes; current compatibility guides point back to this set.

Use Mirage Research and Mirage Home as product names, Chronos for shared implementation and Apate as the repository codename. A session is not a person. An attempt is not successful execution. A rule match is not a calibrated probability. A hash supports integrity checking against a trusted reference, not proof of authorship or custody.

## Planning decisions

| ID | Decision | Rationale |
|---|---|---|
| D1 | Research MVP first | Existing implementation supports a controlled, measurable deliverable. |
| D2 | SSH only for MVP | Additional protocols need independent contracts and a research purpose. |
| D3 | Deterministic state, optional AI artifacts | Models cannot control execution, identity, permissions or evidence truth. |
| D4 | Retain FUSE for v1 | Correct semantics before a disruptive rewrite; reconsider using measurements. |
| D5 | One native research console | Finish one complete workflow before adding frontends. |
| D6 | Remove expertise/identity claims | Existing heuristics do not establish either. |
| D7 | Controlled local deployment | Household/public operations require additional product and operational work. |
| D8 | Gate-based completion | No deadline does not mean unlimited MVP features. |

Each work package records requirements, changed files, test environment/results and limitations. Freeze source/configuration for evaluation. If tests use uncommitted changes, retain a patch hash alongside the commit. Do not attribute such results to the commit alone.

Deferred code is not automatically deleted. Inspect imports, entry points and tests, isolate it from the default path, then remove it only with a documented reason. The backlog now records completed MVP corrections and their limits; deferred features are not implied to be implemented.

## External grounding

Checked 2026-09-25; freeze versions for experiments.

- [Cowrie documentation](https://docs.cowrie.org/en/stable/README.html): established SSH/Telnet baseline with emulation, proxy operation and experimental LLM support. Adding an LLM alone is not a substantiated novelty claim.
- [Paramiko channel API](https://docs.paramiko.org/en/stable/api/channel.html): sends may be partial; local transport acceptance differs from client consumption.
- [MITRE ATT&CK](https://attack.mitre.org/): technique vocabulary for evidence-backed mapping, not an expertise scoring model.
- [NIST IR 8425](https://csrc.nist.gov/pubs/ir/8425/final): informs Home product security requirements; referencing it is not certification.

This is a reviewed baseline, not a guarantee of zero defects. Unknowns remain explicit and release claims require recorded evidence.
