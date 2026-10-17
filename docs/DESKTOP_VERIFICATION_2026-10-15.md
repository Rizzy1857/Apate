# Desktop integration verification — October 15, 2026

Intermediate evidence for the integrated-product working tree. This does not
replace the October 11 frozen release or complete the expanded acceptance scope.

Environment: native macOS app, Docker Engine 29.8.2, Rust 1.99.0. The development
app was built with tests/integration/package_dashboard_macos.sh. Older manual
containers were preserved; the managed project uses separate names and volumes.

| Procedure | Observed result |
|---|---|
| GUI startup | Core, stores and relay start; native UI shows readiness and Redis/PostgreSQL ONLINE. |
| Network boundary | Core has exactly one network, marked internal. Relay publishes only loopback ports 2222, 16379 and 15433. |
| Two real SSH sessions | verify_managed_desktop.py passes pinned-key login, same-path file separation, independent directories, runtime/procfs path rejection and persistent persona existence. |
| Native live operations | Two session UUIDs, usernames, /tmp and /home/ubuntu directories and last command IDs appear; audit rows update and recorded-open count becomes two. |
| Core restart and supervisor recovery | Exact persistent persona snapshot remains unchanged. |
| Native quit | GUI exits; all four managed containers are removed and all four data/evidence volumes remain. |
| Clean GUI relaunch | Containers are recreated; exact persona snapshot is retained; SSH/network verifier passes again. |
| Regression checks (latest) | Python: 262 passed, 7 explicit skips. Rust: 12 passed, 1 opt-in test ignored by default; that real-core export test also passed separately. |

Before/after persona snapshot SHA-256:
f694031a5e35adba260db7c4ea13b94a836c1fdfc7dbfc6ea608cf1c7ef0b17b.
This covers canonical JSON of the stored device records; it is a local comparison
value, not an independently signed attestation.

Testing found and fixed container name/port conflicts, unpublished ports on the
internal network, macOS development signing, stale-file locks, lazy-only persona
creation and cleanup skipped by native quit. Cleanup is now registered in the
GUI exit hook, with a main fallback.

Remaining acceptance work is tracked below; these are intermediate results,
not a declaration that the integrated product is released.

## Persistent runs and live collection additions

Subsequent implementation and tests passed the actual GUI seed/resume/fresh
workflow. Run 7c42e420-f716-4780-b979-351fd235bfe1 retained its synthetic file and
/tmp directory when resumed by session 2d2eefa5-c278-4a2a-9a12-1310d8de49e3.
The GUI fresh action then created run 90c5d520-effd-4295-b668-9222271d96ac at
/home/ubuntu without the earlier file. Both runs finalized to paused after cleanup.

The updated full suite passes 262 Python tests with seven explicit skips; twelve
Rust tests pass. New tests cover concurrent one-use selection, wrong-owner and
profile-mismatch rejection, original-session journal replay, real in-flight
generation status, and stalled/failed collection health.

A native two-session walkthrough now also shows Collection: healthy, pending
audit events zero, watcher event progress and the actual /etc/hostname artifact
job as deterministic/finished. Its persisted provenance records prompt version
2.0-persona in a run namespace. The actual database-pause recovery check passed;
the native UI showed degraded collection and recovered to healthy after unpause.
The Linux/FUSE integration suite also passed (see
../evidence/desktop_checks_20261015/linux.txt).

## Native exports

Both buttons passed in the rebuilt native app for synthetic session
c56d2632-fc4c-4060-b0a3-61920798ebf3. Private raw export contained six hashed
members; the redacted copy contained seven. Every manifest SHA-256 matched.
Directories were 0700 and member files 0600. The synthetic command sentinel
was present in raw and absent from every redacted member. Raw reproducibility
metadata was complete. Local test outputs live under
/private/tmp/mirage-native-export.wgfhEO; this temporary path is not a release
artifact and is not promised permanent retention.

Testing fixed the container-side PostgreSQL port and replaced Docker archive
copy (which could not read the core's tmpfs export) with bounded framed process
transfer, followed by hash verification and completion-marker-last installation.

## Active-core crash and native resume

verify_managed_crash.py forcibly restarted only the managed core with a synthetic
SSH session open. Run 039dc3cc-53e3-4585-aaa3-c7baeb17d533 reconciled to paused
after lease expiry; its persona and /tmp cwd remained unchanged and transient
session ownership was removed. The native Resume button selected this run.
Session c8d24b52-28ee-4ec5-be57-e088a394bec6 then read its original synthetic
/tmp/crash-probe content and restored /tmp. Collection returned to healthy.

## Local model smoke evaluation

The first six-artifact synthetic trial accepted five outputs; notes.txt failed
both transport attempts. Manual inspection found that the automated validator
had accepted shell prompts in .bash_history. This is not valid native history.
The validator now rejects prompt/transcript lines, the prompt explicitly asks
for stored commands only, and a regression test covers this case. The repeated
trial accepted four of six artifacts: history and notes failed bounded model
transport; syslog needed one retry after a cross-OS rejection. The history
failure was reproduced with inline diagnostics: the model reached its 512-token
budget without completing, and truncation was correctly rejected. The subprocess
previously collapsed that into a generic unreachable error. It now returns only
safe fixed failure codes (truncated/incomplete/transport), retaining deadline and
output bounds and circuit-breaker accounting. Notes failures have not been
independently classified. These are not passing AI-readiness results.
Small automated smoke tests are not human realism studies or
proof of hallucination-free output. Deterministic mode remains the default.

## Startup cancellation

The native GUI was closed while displaying Starting isolated services. Its
process exited successfully; a subsequent Docker project-label query returned
no managed containers, while all four data volumes remained. Cleanup can take
around 30 seconds while the service stop timeouts elapse; it is not instantaneous.

The missing-Docker failure case also passed: a test-only nonexistent Docker
socket produced a visible Docker operation failed message, OFFLINE stores and
unavailable operational snapshots, not a false ready state. The app then quit
successfully. No system Docker setting was changed.

Later follow-up, candidate packaging/image checks, capacity/recovery evidence
and the requirements audit are recorded in RELEASE_EVIDENCE_INDEX_2026-10-16.md.
Consult that index for final acceptance rather than this intermediate record.
No fine-tuning, universal attack
coverage, production security certification, or Home-product completion is claimed.
