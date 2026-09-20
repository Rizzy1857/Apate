# Apate hardening review — 2026-09-09

## 1. Architecture reconstructed

Apate is a research SSH deception environment: a small Linux command emulator,
a Redis-backed FUSE filesystem, constrained lazy file generation, and session
telemetry. It is not a real Ubuntu VM, a malware execution sandbox, or an
autonomous defensive agent. Apate/Mirage are project/product labels; Chronos is
the implementation package, not another independently deployed product.

The implemented path is:

```text
SSH client -> Paramiko -> persistent session worker -> command registry
  -> bounded virtual path resolution -> Linux filesystem syscall -> FUSE
  -> caller PID/session lookup -> session-scoped Redis inode/directory state
  -> cached bytes OR known-file generation -> validation -> fenced Redis commit

SSH/FUSE audit events -> bounded process queue -> PostgreSQL audit rows
  -> polling watcher -> Redis session evidence -> PostgreSQL session evidence
```

For example, `cat /etc/nginx/nginx.conf` resolves an existing manifest inode.
If its content is missing and policy permits inference, a generator claims a
lease, uses trusted machine-profile facts, validates the response, and commits
bytes only if the inode and lease are still current. Later reads use the cache.
`cat /made-up-file` does not ask the model to invent a file. Attacker-created
files do not become AI-backed merely by reusing a familiar filename.

Worker PID mapping identifies the session; it is not the isolation mechanism
by itself. Session-specific Redis keys and disabled FUSE data/attribute caches
provide the tested filesystem separation. The worker process is still trusted
application code with real OS privileges, not a hardened security sandbox.

Realistic current uses are controlled honeypot research, teaching deception,
studying command sequences, and testing lazy artifact generation. Public hostile
deployment requires additional containment and recovery work. Arbitrary malware
execution and convincing emulation of every Linux command are outside this MVP.

## 2. Most serious findings

| Severity | Component / root cause | Trigger and impact | Correction implemented |
| --- | --- | --- | --- |
| Critical | FUSE/Redis used globally shared filesystem keys despite session attribution | Two sessions access the same path: one can observe or alter the other's files | Session key adapter covers ordinary commands, Lua and transactions; FUSE selects by registered PID and denies unmapped operations; kernel caches disabled |
| High | Generation lacked reliable ownership and revision fencing | Concurrent first reads duplicate inference; an outstanding model response overwrites a write or resurrects a deleted inode | Expiring token lease, bounded admission, revision/lease-checked atomic commit and conditional release |
| High | Content mutation mixed decoded Redis responses, metadata-only truncate and unsafe blob deletion | Binary data fails to decode, truncation retains bytes, unlink damages another file with identical content | Binary-safe reads, atomic bounded write/truncate, and deferred blob reclamation |
| High | Command filesystem boundary and SSH lifecycle were incomplete | Poisoned working-directory state or symlinks redirect accesses; unavailable mount or blocked worker causes unsafe/unbounded behavior | Protected environment state, mount/path checks, symlink rejection, spawned workers, IPC deadlines and process/resource limits; strict emulator retained |
| High | Audit startup, schema and delivery paths disagreed | Missing database/wrong columns or connection failure prevents evidence collection or silently loses batches | Fail startup when persistence is unavailable; corrected configuration/schema; retry pending batches; independent evidence transactions and acknowledgment before checkpoint advancement |
| High | Generation/resource controls were incomplete | Repeated missing reads, malformed/large model responses or many files consume resources | Expiring session/global inference quotas, response/type/size/line checks, bounded files/writes/inodes, connection/command limits and deterministic fallback |
| High | Dependency pins had published vulnerability advisories | Exposure depends on vulnerable library behavior reached in deployment | Updated cryptography, Paramiko, requests and click; rebuilt and exercised actual SSH with new dependencies |
| Medium | Deployment/CI referenced deleted or absent components; Docker context was unfiltered | Fresh build/start/test fails or copies local artifacts into build context | Repaired imports/config copying/CI, localhost port binding, reduced mounts, added tracked .dockerignore and corrected exporter settings |

These are architectural findings, not claims that every listed trigger was
demonstrated as an end-to-end exploit. Tests below identify what was exercised.
Removing subprocess fallback was part of the pre-existing remediation changes;
this review retained that boundary rather than crediting it as newly introduced.

## 3. Changes made

- Core: scoped Redis adapter, binary-safe content helper, manifest initialization
  completion marker, Lua parent/type/name validation and directory metadata fixes.
- FUSE: session namespace selection, file-handle ownership, normal cleanup,
  real truncate/write behavior and no listing-triggered generation.
- Intelligence: rewritten generation ownership/commit lifecycle; constrained model
  transport, validation and quotas. This structural change was needed because a
  local future alone cannot coordinate independent generators or fence writes.
- Gateway: persistent spawned workers, bounded IPC/input/resources, safe virtual
  path handling, corrected redirection ordering and packet-wise input decoding.
- Persistence/watcher: corrected startup wiring, schema and evidence retry path.
- Deployment/docs: honest MVP scope, required config in image, local-only ports,
  reduced build context, safer Make clean target, usable Python CI and audit job.
- Experimental integrations: dashboard provenance lookup follows session keys;
  simulation event bus starts explicitly and avoids self-delivered duplicates.

Existing user changes were preserved. No commit or staging operation was made.
New source, tests and the previously ignored simulation/logs package must be
included when the changes are committed.

## 4. Tests added or changed

Regression tests use disposable real Redis instances, not the operator's DB.
They cover cross-session Lua/transaction/blob isolation; concurrent generation;
write/delete/replaced-lease supersession; cached empty fallback; runtime file
eligibility; binary truncate and concurrent writes; shared-blob unlink; invalid
parents/names; bounded malformed model output; traversal/symlinks/protected
environment; redirection ordering; and short-file head behavior.

The 500-request deterministic stress test now exercises real Redis state.
The legacy manifest entry point no longer flushes localhost Redis or calls a
removed private API. Evidence verification uses the isolated Redis fixture and
the new successful-flush acknowledgment contract.

The Linux integration script exercises two real Paramiko clients, spawned
workers and a kernel FUSE mount: deterministic files, private session writes,
truncation, blocked shell execution, inaccessible runtime paths, multi-command
input, and PostgreSQL evidence for sessions started during that test run.

## 5. Verification

- Real Linux SSH/FUSE/PostgreSQL integration: passed against the rebuilt image,
  including Paramiko 5.0.0 and cryptography 50.0.0.
- Earlier complete host Python 3.13 suite: 34 passed, 7 explicitly skipped;
  separate updated evidence verification: 1 passed.
- Earlier container Python 3.11 suite: 34 passed, 7 skipped.
- Final container Python 3.11 run (`pytest tests
  tests/verification/verify_evidence_collector.py -q --tb=short`): 34 passed,
  7 skipped, 4 Pydantic deprecation warnings. `pip-audit -r requirements.txt`:
  no known vulnerabilities found in the resolved Python dependencies at scan time.
- Python compileall, git diff --check and Docker Compose config: passed.
- Rust dashboard cargo check --offline: passed.
- Docker build: passed; excluding local outputs reduced the observed context
  from roughly 2.03 GB to approximately 544 KB before subsequent small edits.

Seven legacy tests require explicit opt-in because they modify external Redis
or stop named containers. Skips are not passes. No live Ollama generation,
full monitoring/UI stack, GitHub-hosted CI run, comprehensive load test,
container escape assessment or power-loss recovery campaign was performed.
Mocked inference tests establish code behavior, not real-model coherence.

## 6. Remaining risks and trim candidates

- The application still needs privileged FUSE access and workers use real
  runtime privileges. Strict command emulation is not proof of containment.
- Audit queues are bounded but not crash-durable; overflow can lose events and
  uncertain commits/replay can duplicate them. Credential capture needs an
  explicit retention, access-control and redaction policy.
- Reaping handles normally observed sessions; a core crash can leave orphan
  namespaces. Partial manifest recovery is not exhaustively tested, including
  directory metadata reconciliation. Write-allocation accounting is conservative
  and does not constitute a complete Redis memory quota.
- Shell flags, permissions, process/network output and filesystem semantics
  remain partial and fingerprintable. Heuristic threat labels are not reliable
  proof of attacker intent or skill.
- Validation constrains model authority and output shape, not every semantic
  contradiction. Real model latency/coherence still needs measurement.
- World simulation still has a baseline/global state path and is not demonstrated
  to update every session coherently. The native dashboard is experimental, and
  Rust Layer 0 remains unintegrated. These are the strongest candidates to move
  outside the supported MVP or remove after choosing a product scope.
- Older historical documentation, simplistic/fixed command responses and unused
  experimental paths are not evidence of implemented production capabilities.
- Mutable image/model tags, local default credentials, dependency advisories
  published after this scan, and base-image OS packages remain operational risks.

The useful core is SSH emulation + session filesystem + lazy artifacts + durable
enough laboratory telemetry. Additional layers earn their maintenance cost only
if an end-to-end test shows the behavior they contribute to that core.

## 7. Recommended next work

1. Establish a dedicated disposable VM/network boundary, restrict egress and
   service access, minimize privileges, and test containment before exposure.
2. Make audit delivery crash-durable and idempotent; define credential handling.
3. Add restart/orphan recovery and Redis outage tests with explicit memory and
   lifetime budgets for all session state.
4. Pick a small supported command/OS profile and test cross-command coherence,
   permissions and realistic failure behavior against that contract.
5. Run live-model latency, malformed-output and semantic-coherence evaluations;
   pin model/image artifacts and exercise Linux integration in CI.
6. Remove or separately package Layer 0, world simulation and native dashboard
   unless they have a measured role in the supported deployment.
