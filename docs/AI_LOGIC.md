# Mirage artifact-generation logic

Reviewed 2026-09-25. This describes current decision boundaries without treating pseudocode as implementation proof. See [AI architecture](AI_ARCHITECTURE.md) and [verification](VERIFICATION_PLAN.md).

## Decision sequence

1. Read inode metadata. Missing inode and directory reads return filesystem errors.
2. Return an existing content-addressed blob immediately.
3. Return empty content for runtime files that are not approved deterministic/AI manifest artifacts.
4. Submit or join an in-process future. If the bounded worker pool has no slot, return a retryable timeout result to FUSE.
5. Claim the Redis generation lease or wait up to approximately ten seconds for its owner to commit.
6. Re-read inode metadata and revision after claiming the lease.
7. Build trusted machine facts from the Ubuntu profile and resolve the file policy.
8. Render deterministic content, intentionally skip, call the selected local model within quotas/deadlines, or use a fallback.
9. Validate model output. Retry once within the job deadline and quota; label any fallback distinctly.
10. Commit only if the inode exists, its revision is unchanged, it has no newer content, and the lease token still matches.
11. Store the blob by SHA-256 and attach provenance. Release only the matching lease.

The orchestrator uses a per-session and global per-minute quota. Quota counters limit model calls, not all reads. Generated artifacts are bounded by validator/content limits. The full release must measure actual memory, process, and request behavior under concurrent sessions.

## Policy and validation

File class derives from the manifest/path and chooses a distribution in `config/generation_policy.yaml`. Random category sampling means two uncached preparations can differ. Experiments must preserve selected categories or seeds where possible and record all trials.

Validation checks type, encoding/size/line limits, refusal or formatting artifacts, and file-specific semantic rules. Nginx validation requires coherent contexts and rejects known invented backends/includes. Other validators have different depth. “Validated” means these rules passed; it does not mean the file is universally correct or safe.

Prompt inputs are trusted profile facts and a sanitized manifest path. Attacker-created runtime paths do not become AI-backed after recreation. Model outputs remain untrusted until validation and never enter shell execution.

## Result terminology

| Source | Meaning |
|---|---|
| `template` | Deterministically rendered content |
| `llm` | Model output accepted by the current validator |
| `fallback` | Degraded deterministic content after skip, quota, rejection, or failure as applicable |

Reports must retain source and validation fields. A cached read measures storage retrieval, not model latency. A fallback must not be counted as accepted generation. A successful generation must not be counted as improved deception without the controlled evaluation in [VERIFICATION_PLAN.md](VERIFICATION_PLAN.md).
