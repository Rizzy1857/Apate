# Integrated desktop verification — October 16, 2026

This is a release-candidate checkpoint, not final integrated-product acceptance.
The October 11 MVP evidence remains historical and unchanged.

Initial checkpoint results (later checks and counts are in the release index):

- Default Python regression suite: 262 passed, 7 explicit skips.
- Explicit local HTTP integration suite: 4 passed, covering stalled headers,
  stalled body, token-limit truncation and incomplete streams. These exercise
  the real inference child process and local HTTP transport. Truncated and
  incomplete responses retain safe failure codes and increment the circuit
  breaker; stalled requests leave no inference transport process running.
- Rust suite: 12 passed, 1 opt-in real-core export test ignored by default.
  The real-core export and native export buttons passed on October 15; they
  were not rerun by this unit-test invocation.
- History validation regression no longer randomly samples an empty category.
- `git diff --check` passed.

The first HTTP test invocation was blocked by sandbox socket permissions before
the code could be exercised. The approved loopback invocation passed. Neither
that permission failure nor the local-model diagnostic approval-review timeout
is counted as a product failure or a passing test.

See DESKTOP_VERIFICATION_2026-10-15.md for native startup/shutdown, startup
cancellation/failure, run resume/fresh, core crash recovery, collection-health
failure/recovery, isolation and raw/redacted export observations.

The notes-model diagnostic completed on retry (60 output bytes, accepted by the
validator). This is one synthetic success, not a reliability estimate. Earlier
failures remain part of the evidence; deterministic mode remains the default.

The first candidate, release_candidate_20261016_desktop, contains 190 files and
has archive SHA-256
00e5b9536c339b2652c1fc0458d2f2bd3435d9193532193ad3545573ee8a0b6f.
Its extracted Python suite passed (262 passed, 7 skipped). Rust returned 11
passes, one failure and one ignored test: immediate lock reacquisition failed
in the parallel suite. The recovery assertion now allows at most two seconds
for transient inherited file descriptions to close during concurrent process
spawning. It still verifies exclusivity while the original owner holds the
lock. This changes test timing only, not production ownership checks. The first
candidate is retained as superseded evidence, not silently overwritten.

Subsequent checks verified the replacement candidate, packaging and a freshly
rebuilt image, refreshed the core-image scan, and passed persistent-run short
load and recovery procedures. Current Python regressions: 264 passed, 7 skips.
The extended soak and final source/evidence reconciliation are still pending;
see RELEASE_EVIDENCE_INDEX_2026-10-16.md for the authoritative final verdict.
No fine-tuning, hallucination-free inference, production security certification
or completed Mirage Home product is claimed.
