# Integrated product implementation

The October 11 frozen Research MVP remains historical verified evidence. The
current changes start a new product iteration; they are not covered by its
release verdict.

## Implemented foundation

- Explicit trusted device purpose and user roles in the Ubuntu profile.
- A profile-content-addressed, schema-versioned Redis device record, outside
  disposable session namespaces. The first initialization fixes its reference
  time; concurrent initializations cannot overwrite it.
- Immutable per-session machine snapshots; session cleanup retains the device.
  Profile changes create a different device revision, not a silent migration.
- Artifact prompts include identity, purpose and roles even for notes.
- SSH workers publish operational context at startup and command completion:
  effective identity, canonical current directory and last command ID. These
  records are projections, not substitutes for durable audit events. Cleanup
  removes them; they do not authorize reconnect/resume.

Device durability follows Redis persistence configuration (Compose uses AOF
every second and a named volume). This is not a new independent backup store;
loss of that volume loses the device record. Legacy session snapshots remain
unchanged until their normal cleanup. Old profile revisions are retained.
The operator can start a fresh filesystem run or explicitly resume
a paused compatible run; deletion/retention of old records remains an operator
storage policy rather than an automatic data purge.

## Verified implementation and remaining acceptance

Progress on October 15: the native Live Ops view now renders session context
snapshots (effective username, current directory, last command and update time).
Redis snapshots are refreshed every two seconds with a three-second collection
deadline and an explicit 1,000-context capacity error, using SCAN rather than
KEYS. Each successful refresh replaces the list, reconciling removals and missed
updates after reconnect. Failed refreshes/disconnections retain visibly stale
data; an eight-second freshness window also catches silent stalls. Audit pause
does not pause this operational state display. Operational snapshots do not prove
a socket is alive. The native walkthrough verified the live contexts. Generation
resolution jobs and collection heartbeat/outbox/watcher state are now implemented
and passed native healthy/degraded/recovered collection verification.

1. Verified GUI live-operations rendering of context, generation and collection health,
   with missed-event reconciliation and explicit stale/disconnected states.
2. Verified GUI-managed process startup/readiness, ownership-aware shutdown and errors.
3. Persistent-run resume/fresh controls are implemented and passed the native
   three-phase seed/resume/fresh procedure. New shells receive fresh runs by
   default; only a one-use operator selection can resume a paused compatible
   device run. Files and cwd survive; environment variables remain per connection.
4. Generation provenance and bounded local-model evaluation are recorded; live
   Linux containment, restart/persistence and named GUI procedures passed.
5. October 19: the authenticated extended soak passed; source/image identity,
   Linux integration and private standalone staging startup were reconciled.
   See RELEASE_EVIDENCE_INDEX_2026-10-19.md for the bounded private-staging verdict.
   No fine-tuning
   has been performed; this iteration grounds the existing model in state.

Native acceptance evidence is in DESKTOP_VERIFICATION_2026-10-15.md; current
capacity/recovery results are in PERSISTENT_CAPACITY_2026-10-16.md and the
requirement mapping is in INTEGRATED_ACCEPTANCE_AUDIT_2026-10-16.md. Native
raw/redacted exports and active-core crash followed by operator-selected resume
have passed. The Python suite now has 272 passing tests and seven explicit skips;
the Rust suite has thirteen passing tests and one ignored opt-in real-core test.
Earlier native export checks are separate evidence. An initial six-artifact local model smoke trial exposed malformed
history that passed validation; prompt and validator checks were tightened.
Startup failure/cancellation passed native checks. Model re-evaluation still
shows bounded generation failures; truncation is now distinguishable from
connectivity failure. A later notes diagnostic succeeded, but model reliability
is not certified. Deterministic mode remains the baseline. The October 19
predeployment verdict is restricted to private ARM64 testing with documented
residual core risks; it is not a public-release or model-reliability certification.

## GUI lifecycle implementation and verification

The native entry point now starts a background Compose supervisor by default.
It provisions POSTGRES_PASSWORD and GRAFANA_PASSWORD, uses the repository directory
(or CHRONOS_PROJECT_DIR), and manages only the chronos-gui project. Startup
waits for container health and checks the FUSE mount and SSH banner. Status and
sanitized failure messages appear in Live Ops. CHRONOS_MANAGE_STACK=0 retains
connect-only mode with explicit backend configuration.

An OS-held .local-deploy/gui.owner lock prevents concurrent supervisors and
releases automatically when the process exits. Recovery verifies each existing
container's Compose project, repository working directory and allowed service
before resuming it. Normal GUI exit stops and removes its service containers
without deleting volumes. Native startup, shutdown and persistence checks passed.

First-run setup now creates independently random 256-bit passwords using the OS
random source, saves them in .local-deploy/gui-credentials.json with mode 0600,
and reuses them on later launches. Explicit initial credentials are supported;
later mismatches are rejected rather than silently rotating a retained database's
password. Symlink/non-private credential files are rejected. Credentials never
appear in status output. Managed mode selects local database endpoints explicitly.
Closing the window cancels the build/readiness child process before cleanup.
Twelve Rust tests pass, including credential reuse/permissions, timeout and startup
cancellation checks. The native GUI was verified on macOS; the core's Linux/FUSE
procedures are separate and do not certify a Linux desktop GUI. Initial Docker
unavailability was resolved before the recorded native checks. Unit tests alone
are not treated as native GUI acceptance.

Live startup testing found and corrected conflicts with old manual container
names and host Redis port 6379. Managed containers now use mirage-gui names.
On this Docker Desktop host, internal-network services do not publish usable
host ports. A fixed-destination relay exposes only loopback SSH 2222, Redis
16379 and PostgreSQL 15433; the core and stores stay on the internal network.
The relay has a read-only root, no capabilities, UID 1000 and bounded resources.
Its destinations are constants; client bytes cannot select an upstream.

The local macOS package script applies an ad-hoc signature after each rebuild,
required to launch a replaced development binary. Signing/notarization for
distribution remains outside this local development package.

The native walkthrough now shows Redis/PostgreSQL ONLINE and managed fake-system
readiness. The controlled two-session verifier passed pinned-host-key login,
same-path file separation, independent directories, and denial of runtime/procfs
reads. The GUI displayed one session at /tmp and its peer at /home/ubuntu with
their last command IDs. Device identity is now initialized at admission even
when no generated file is read. A persona snapshot hash remained unchanged across
core restart and GUI recovery. At that stage the Python suite passed 249 tests
with seven explicit skips; the current count is recorded above.

Native quit exposed that cleanup after run_native alone was insufficient on this
platform. Cleanup is now also registered in the application on_exit hook, with
the UI receiver disconnected before joining backend workers. Shutdown completion
and a subsequent fresh-start persistence check both passed. See the
[desktop verification record](DESKTOP_VERIFICATION_2026-10-15.md) for observed
procedures and remaining acceptance work.
