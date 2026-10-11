# G3 evidence assessment — 2026-10-08

## Decision

G3 passes for the declared Research MVP lifecycle and evidence boundary. Known submissions, stages and filesystem effects reconcile exactly in the exercised cases; interrupted work is recorded as unknown rather than inferred successful.

## Exercised cases

- A submitted command begins with outcome `unknown` and becomes successful or failed only after a matching result event.
- Unknown, blocked, failed and successful commands retain distinct outcomes and stable command IDs.
- Every executed pipeline stage is retained, including an earlier failure when the final stage succeeds; skipped conditional branches are explicit.
- Filesystem events copy only the current session's validated command ID and origin. Missing/invalid attribution remains explicit rather than being borrowed from another command.
- Short transport writes are retried until the payload is accepted. A zero/failed write records the exact locally accepted byte count and makes delivery uncertain.
- A real killed worker closes with an interrupted lifecycle and leaves a command submitted immediately around failure as `unknown`.
- Whole-core `SIGKILL` recovery reconciles admitted sessions as interrupted/orphaned without duplicate event IDs or inherited session state.
- PostgreSQL outage preserves SQLite-outbox events; a simulated failure after database commit deduplicates the uncertain retry.
- Abrupt outbox-process exit preserves admitted records. Reusing a deterministic event ID is idempotent only for the same byte-stable payload.
- A state mutation committed before audit admission remains in the Redis mutation journal and is replayed idempotently. A full audit spool rejects the mutation before state change.
- Lifecycle open/close recovery is first-writer-wins and idempotent; cache outage does not classify every session as dead.
- Real Linux raw export reconciles every submitted command to result events and every supported file effect to the current command; no unmatched result/effect IDs remain.

## Interpretation

The exact counts are those produced by each frozen fixture or disposable run. An accepted command submission is evidence of intent, not completion. A generated response and a locally transport-accepted response are separate counts. TCP/SSH delivery beyond local acceptance is never claimed.

## Limitations

- A real network stack does not deterministically expose every possible short-write boundary, so byte-level short writes/disconnects use a deterministic channel fault fixture; real worker and whole-core termination exercise process-level uncertainty.
- PostgreSQL is eventually idempotent with the SQLite outbox, not part of a distributed transaction with Redis.
- Simultaneous loss of Redis and its configured persistence remains outside the application-process guarantee.
- New event writers or lifecycle boundaries require new reconciliation fixtures before release.
