# Mirage artifact-generation roadmap

The old Phase 2 roadmap has been retired. Current work is tracked in [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md), especially W4, and evaluated through G5 in [VERIFICATION_PLAN.md](VERIFICATION_PLAN.md).

The order is:

1. Make the deterministic Research MVP operate with no model service.
2. Repair the generation deduplication fixture without weakening validation.
3. Freeze the required artifact list and define valid versus intentionally degraded treatments.
4. Verify prepared-bundle invalidation against source, policy, prompt, validator, profile and model changes.
5. Run repeated per-artifact cold, warm and concurrent trials, recording rejection, fallback, latency and provenance.
6. Compare deterministic and prepared-AI treatments using the published rubric.

Cloud providers, attacker-skill-driven routing, autonomous learning, AI session summaries and lazy generation as a default interaction path are outside the MVP. See [RESEARCH_FUTURE.md](RESEARCH_FUTURE.md) before expanding this scope.
