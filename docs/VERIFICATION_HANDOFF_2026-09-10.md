# Verification handoff — 2026-09-10

This is an evidence ledger for documentation updates, not a production-readiness
certificate. The hardening goal remains open. Preserve these distinctions when
updating README, STATUS, FINAL_PROJECT_SUMMARY, ONBOARDING and roadmap material.

## Verified observations

- Strict SSH command emulation; unknown commands do not execute host programs.
- Linux integration passed after rebuilding: real SSH/FUSE interaction,
  cross-session isolation, worker containment, audit retry and idempotency.
- Worker containment test denies new sockets, fork, exec and privilege regain;
  chroot hides application files. The privileged FUSE daemon is outside this
  worker boundary. This is not a container-escape assessment.
- Host regressions: 54 passed / 7 legacy infrastructure tests skipped, followed
  by a separately passing full write-budget test (one additional test).
  Four Pydantic deprecation warnings remain. Skips are not passes.
- Normal-entry-point PostgreSQL outage run: 32 sessions, 120-second workload,
  PostgreSQL paused for approximately 30 seconds, 1,526 completed command
  sequences and 1,526 audit records, 32 final evidence records, cleanup passed.
  Median 2.570 s, p95 2.794 s, maximum 3.118 s; core limited to 2 CPUs / 2 GiB.
  Sequence: `echo TOKEN > /tmp/probe; cat /tmp/probe; cat /etc/hostname`.
  These are sequence-to-prompt timings, not individual-command timings.
- Previous diagnostic-entry-point outage run also passed: 1,509 sequences,
  p95 2.918 s. Earlier runs stalled; their original cause remains unproven.
- Redis stop/start: 32 sessions closed, 113 confirmed commands all retained in
  145 admitted audit attempts, orphan state reclaimed, new-session isolation
  passed. Fixes close SSH before external cleanup, observe worker death while
  idle, and resolve the worker's Redis address before entering chroot.
- Core SIGKILL/restart: 32 sessions, all 67 confirmed commands retained among
  97 admitted attempts, orphan cleanup and new-session isolation passed.
  Admitted attempts are not proof of successful command execution. The test
  does not prove every interrupted session gets a finalized summary.
- Full 16 MiB cumulative write budget and 1 MiB file limit exercised against
  disposable Redis; rejected writes preserved prior bytes and metadata.
- Compose configuration validates with explicit test credentials. A disposable
  internal-network core had no published ports; outbound TCP to 1.1.1.1:443
  failed with ENETUNREACH. This is not a complete egress or host-access audit.
- Docker Scout critical/high scan of ARM64 image
  `sha256:6d22d9b6a60499b2e1c4790f8f98150b29ce66123968a0c5d929300750ed4b31`:
  154 packages, 0 critical, 1 high: zlib CVE-2026-85091, no fixed version
  reported. Medium/low severities were filtered; do not claim zero at those
  severities. No suppression or claim of non-exploitability was made.

## Real model evaluation

Actual local Ollama plus disposable Redis, using the manifest/orchestrator,
validator, provenance and cache. This was not an AI-enabled SSH/FUSE end-to-end
test. Model digests:

- llama3:8b: `365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1`
- llama3.2:3b: `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`

The old non-streaming request routinely timed out. Bounded streaming now rejects
incomplete/token-truncated output and enforces size and elapsed-time limits.
The first filesystem read still waits at most approximately 10 seconds, then
can return retryable EAGAIN while background work continues.

Latest run after path-specific nginx checks and shorter excerpt prompts:

| File | Source | Time until content settled | Cached read |
| --- | --- | ---: | ---: |
| auth.log | empty fallback | 30.072 s | 0.995 ms |
| syslog | empty fallback | 30.032 s | 0.735 ms |
| .bash_history | empty fallback | 30.043 s | 0.592 ms |
| notes.txt | validated LLM | 3.832 s | 0.558 ms |
| nginx.conf | file-specific fallback | 10.107 s | 0.481 ms |
| index.html | file-specific fallback | 0.003 s | 1.025 ms |

An earlier streaming run produced nginx and HTML via the model, but manual
review found an invented backend and a missing include file despite the generic
validator accepting it. New regression checks reject those contradictions.
File-specific fallbacks replace the generic nginx/HTML placeholder. They are
still explicitly labelled fallback, not validated LLM output.

The evaluator's passing assertion requires only one actual LLM success; it does
not certify every file class, semantic coherence, or acceptable latency.

## Remaining acceptance work

- Reliable real-model generation and cross-file coherence, including the
  advertised port 443 versus the static-site fallback's port-80 configuration.
- Full supported-command/flag contract and end-to-end consistency coverage;
  command emulation remains partial and fingerprintable.
- Final deployment boundary review beyond the single external-address check;
  no public exposure, escape-proof claim or full monitoring-stack claim.
- Decide how interrupted sessions are represented in final evidence, and test
  that representation. Crash-retained audit rows are not finalized summaries.
- Follow the remaining zlib advisory; do not silently waive it.
- No human alpha test measured time until an attacker discovers the honeypot.
  `detection_status` currently means suspicious attacker behavior was flagged,
  not that the attacker discovered Apate. Session duration is not MTTD.

## Instructions for the documentation editor

Use this ledger and current source, not historical completion checklists. Describe
Apate as a hardened research SSH-emulation MVP. Separate implemented, tested,
experimental and unverified capabilities. Keep the world engine, monitoring and
native dashboard distinct from the supported core; Rust Layer 0 still exists
but is not demonstrated as an integrated core path. Do not claim general Linux
execution, public-deployment readiness, reliable AI generation, or measured MTTD.
Preserve concurrent documentation changes and mark stale claims explicitly.
