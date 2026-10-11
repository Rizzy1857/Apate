# G5 deterministic and prepared-AI assessment — 2026-10-08

## Decision

G5 passes its operational-safety criterion. The Research MVP works without inference, rejects invalid required artifacts, prevents generation from overwriting participant state and treats prepared AI as an explicit offline experimental treatment. This is not a claim that AI is more realistic.

## Verified behavior

- Base Compose starts the core in deterministic mode without the optional inference service.
- Deterministic mode does not construct or call an inference transport.
- All six AI-backed profile paths have non-empty validator-accepted deterministic templates.
- Unknown inference modes and unknown artifact treatments fail closed.
- A prepared treatment must name a complete, current, schema-versioned bundle whose fingerprint covers generation inputs and whose model tags resolve to immutable digests.
- Missing, legacy, malformed, incomplete or fingerprint-mismatched bundles are rejected before filesystem installation.
- Concurrent orchestration deduplicates one generation, and generation cannot overwrite a newer participant write, delete or replaced lease.
- Deadline handling terminates and reaps a slow transport; incomplete, malformed, oversized, NUL-containing and truncated model responses are not committed.
- Runtime reads consume installed content and do not regenerate it. Concurrent prepared reads and participant writes remain bounded by the same fenced state operations.
- The frozen 30-trial valid-only engineering comparison retained all attempts: prepared AI accepted 172/180 after at most two attempts; deterministic templates accepted 180/180.

## Research boundary

Independent blinded plausibility scoring was not performed. Therefore the MVP makes no AI-superiority, attacker-engagement or realism-improvement claim. Prepared AI remains optional experimental material; deterministic artifacts are the release baseline. A later paper may add blinded review without reopening this operational gate unless it changes runtime code or the declared treatment.
