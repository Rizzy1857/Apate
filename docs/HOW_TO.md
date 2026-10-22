# Mirage Research operator guide

Reviewed 2026-10-22. The October 19 ARM64 candidate passed its documented predeployment gates for **private authorized testing only**. This is a bounded SSH emulator, not a full Linux VM, trained attack detector or household security product. See [current test coverage](WORKING_REVIEW_2026-10-22.md) and [residual risks](DEPLOYMENT_SECURITY_REVIEW_2026-10-19.md). Public exposure is not approved.

## Choose a deployment

| Mode | Purpose | Endpoints and persistence |
|---|---|---|
| Managed desktop | GUI owns local startup/shutdown | Loopback SSH 2222, Redis 16379, PostgreSQL 15433; persistent runs |
| Base Compose | Developer-controlled services | Loopback SSH 2222, Redis 6379, PostgreSQL 5433; fresh namespaces by default |
| Standalone staging | Private ARM64 Linux VM | Loopback SSH 2222; no database host ports; persistent runs |

Do not run two stacks on port 2222. Do not merge standalone staging with base Compose. The clean October 19 Redis/PostgreSQL scans apply only to hardened staging images, **not** the older base Compose images used by desktop development. The privileged core retains accepted risks in all modes.

Run commands from the repository root. Docker access is administrator access; participants must have neither Docker access nor a host shell.

## Managed desktop: start to finish

1. Install Rust/Cargo and Docker Desktop on macOS. Start Docker and wait for `docker info` to succeed. Linux source launch requires Docker Engine with `/dev/fuse`; Windows managed startup is unsupported.
2. Close an existing Mirage window before rebuilding:

   ```sh
   bash tests/integration/package_dashboard_macos.sh
   open .local-deploy/Mirage.app
   ```

   This is an ad-hoc-signed development bundle, not a notarized distribution. Keep the checkout in place. Alternatively launch from source with `cargo run --locked --manifest-path src/chronos/dashboard/Cargo.toml`.
3. Wait for readiness, then inspect Live Ops. The GUI starts its own core, database, Redis and loopback relay. A startup error is not readiness; do not launch another supervisor to bypass it.
4. Preserve `.local-deploy/gui-credentials.json` and the named volumes together. First launch creates private credentials; later launches reuse them. Legacy files gain a Redis password without rotating database credentials. Deleting this file does not reset an existing database password.
5. Connect through SSH as below. After disconnecting, inspect finalized history and export evidence.
6. Quit normally: managed containers stop and their named volumes remain. Relaunch to inspect paused runs and retained persona. Do not remove supervisor files or unrelated containers blindly after a crash.

## Manual development: credentials first

For a **new disposable deployment**, generate independent credentials without printing them:

```sh
export REDIS_PASSWORD="$(openssl rand -hex 32)"
export POSTGRES_PASSWORD="$(openssl rand -hex 32)"
export GRAFANA_PASSWORD="$(openssl rand -hex 32)"
```

Securely retain these values before closing the shell. For existing volumes load the original credentials instead. Changing an environment variable does not rotate an initialized PostgreSQL password. For Azure use [AZURE_STAGING.md](AZURE_STAGING.md), not the base Compose commands below. That guide covers image digests, private configuration, startup and administrator tunneling; actual Azure host acceptance remains separate from local tests.

## Preflight

Use a supported Linux Docker host with FUSE for the full path. Review both `docker-compose.yml` and any local override. Define `REDIS_PASSWORD`, `POSTGRES_PASSWORD` and, because current Compose interpolates it even for the optional monitoring profile, `GRAFANA_PASSWORD`. Base Compose is the deterministic no-model treatment; Ollama is optional.

Validate configuration without sharing its rendered secret values:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs core-engine
```

To validate/start the portable deterministic graph without an automatically loaded local override:

```bash
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml up --build -d
```

For experimental lazy Ollama generation, record the model digest and use:

```bash
CHRONOS_INFERENCE_MODE=ollama docker compose -f docker-compose.yml --profile inference up --build -d
```

Selecting the profile alone does not change the core mode; `CHRONOS_INFERENCE_MODE=ollama` is deliberate. Prepared-artifact generation also explicitly requires Ollama. Invalid mode values stop generation setup rather than silently choosing a backend.

Prepared artifacts are a separate, explicit treatment. The research network is internal: **do not expect `ollama pull` inside it to reach the internet**. Provision the cache before the experiment. A development-only provisioning sequence, using a unique unused container name, is:

```sh
docker volume create mirage-model-cache
docker run -d --name mirage-model-provision -v mirage-model-cache:/root/.ollama \
  ollama/ollama@sha256:57f573b47f1f71ebb445789f279fe3e596a8beab182f7cf486db9205bad87c5a
docker exec mirage-model-provision ollama pull llama3.2:3b
docker exec mirage-model-provision ollama pull llama3:8b
docker exec mirage-model-provision ollama list
docker stop mirage-model-provision
docker rm mirage-model-provision
```

This temporary container has no published ports or research-network membership. Downloads need internet, disk and RAM; they were not repeated in the October 22 review. Keep the cache. Create a local `models.override.yml` with:

```yaml
volumes:
  ollama-data:
    external: true
    name: mirage-model-cache
```

Inspect configuration, start the isolated model service, prepare the bundle, and select it explicitly:

```bash
docker compose -f docker-compose.yml -f models.override.yml --profile inference config --quiet
docker compose -f docker-compose.yml -f models.override.yml --profile inference up -d redis-store db-store ollama
docker compose -f docker-compose.yml -f models.override.yml --profile inference exec ollama ollama list
docker compose -f docker-compose.yml -f models.override.yml --profile inference run --rm \
  -e OLLAMA_HOST=ollama core-engine \
  python3 -m chronos.intelligence.prepared_artifacts
CHRONOS_ARTIFACT_TREATMENT=prepared docker compose -f docker-compose.yml -f models.override.yml --profile inference up --build -d
```

Record the exact model digests after pulling them. The default is `CHRONOS_ARTIFACT_TREATMENT=deterministic`, which never loads a stored prepared bundle. Selecting `prepared` without a complete current bundle fails before filesystem initialization. Changing the treatment does not replace files in an already initialized session namespace.

For lazy generation with this cache, pass the same override and inference profile while setting `CHRONOS_INFERENCE_MODE=ollama`. Keep the same Compose files for stop/restart too. Record rejected trials, fallback counts, hardware and immutable model identities; bounded fallback tests do not establish model quality or training. Optional `monitoring` and `experimental` profiles are developer tools outside staging acceptance. Inspect their definitions before enabling; HTTP/Layer 0 and Home are not established product entry points.

Do not infer readiness from a running container alone. Confirm Redis/PostgreSQL health, a mounted FUSE path, the SSH listener, the audit worker, and absence of repeated delivery errors.

## Controlled SSH session

Connect to the configured local endpoint (base Compose publishes loopback port 2222; a local override may proxy it differently):

```bash
ssh -p 2222 ubuntu@127.0.0.1
```

Inspect and accept the expected development host-key fingerprint rather than globally disabling host-key checking. The explicit deception policy accepts the claimed password/public-key username as an observation while using the configured profile identity inside the emulator. Evidence records claimed and effective identities separately. This is not a production authentication design, and passwords are never recorded.

Use only the versioned surface in [COMMAND_CONTRACT_V1.md](COMMAND_CONTRACT_V1.md). The bounded G1 contract passed both its reference matrix and real SSH/FUSE reconciliation. Do not use a direct `docker exec` shell as evidence of an attributed participant session; PID-based session registration is part of the supported SSH path.

Try this harmless sequence in the interactive shell:

```sh
whoami
pwd
hostname
cat /etc/passwd
echo research-check > /tmp/research-check
cat /tmp/research-check
cd /../../
pwd
exit
```

The final directory remains the fake `/`, not the host filesystem. SSH exec (`ssh ... command`), SFTP/SCP and forwarding are denied. Input lines over 8,192 UTF-8 bytes are discarded through newline. This is an emulated command registry, not arbitrary host execution.

### Persistent runs and persona

In managed Live Ops, write a marker and change directory, disconnect, then wait for the run to become paused. Select that paused run for the next shell and reconnect within 60 seconds. Verify marker, directory and device identity. The selection is one-use and is **not tied to a verified identity**: only arm it when you control the next connection. Another participant can consume it.

Start fresh to create an independent filesystem while retaining older runs. Fresh runs must not inherit the marker. Profile-content changes create a new device revision. Canonical persona/device facts and immutable session snapshots ground generation; the model does not own state. Shell environment variables remain connection-local. Persistent runs are enabled in managed/staging modes, not base Compose by default. Retained runs continue consuming storage.

Sessions are limited to one hour, 1,000 submitted commands and 120 seconds idle time. The worker's cumulative CPU allowance defaults to 300 seconds; `CHRONOS_WORKER_CPU_SECONDS` accepts 60–600 seconds. An independent supervisor renews the 120-second PID attribution lease. Expired, replaced or closed leases are not revived. Host/VM suspension can exceed these leases: keep the host awake during experiments and treat disconnects after suspension as interruptions, not continuous operation. A sustained experiment should reconnect before the session limits and report those planned rotations.

## Evidence and UI

PostgreSQL audit rows and the SQLite outbox have different states. “Recorded open” means the latest durable lifecycle event is open; it does not prove a socket is currently reachable. Finalized history is paginated. Exports represent a PostgreSQL snapshot and omit pending spool events; inspect `run_record.json`, `report.md` and `complete.json`.

Set reproducibility identifiers before a formal run:

```bash
export APATE_RUN_ID='<frozen run identifier>'
export APATE_SOURCE_REVISION='<commit plus patch identity>'
export APATE_CONFIGURATION_DIGEST='<sha256 of frozen effective configuration>'
export APATE_PROFILE_DIGEST='<sha256 of frozen profile>'
export APATE_MODEL_IDENTIFIER='<model name and immutable digest, or deterministic-none>'
```

The dashboard provides separate “private raw” and “redacted copy” actions. The CLI equivalent is:

```bash
python -m chronos.watcher.export_report --session-id "$SESSION_ID" --output "$NEW_FOLDER" --mode raw
python -m chronos.watcher.export_report --session-id "$SESSION_ID" --output "$NEW_REDACTED_FOLDER" --mode redacted
```

Each destination must not already exist. Raw bundles may contain commands, paths, usernames, addresses or other secrets and must remain private. Redacted bundles use `apate-structural-allowlist-v1`, omit free text by default and preserve only pseudonymous correlation. They disclose omissions and equality leakage in `redaction.json`; they cannot guarantee removal of every arbitrary secret. Preview a redacted bundle before sharing it.

For manual base Compose, the CLI can run inside the core without installing host Python dependencies. Choose a real session UUID from history; use a new container path and a new host destination. Container PostgreSQL uses **5432**, not the host CLI default 5433:

```sh
SESSION_ID='REPLACE_WITH_SESSION_UUID'
docker compose -f docker-compose.yml exec -e POSTGRES_PORT=5432 core-engine \
  python3 -m chronos.watcher.export_report --session-id "$SESSION_ID" \
  --output /tmp/export-unique-raw --mode raw
docker compose -f docker-compose.yml cp core-engine:/tmp/export-unique-raw ./export-unique-raw
chmod -R go-rwx ./export-unique-raw
```

Copy before stopping: `/tmp` is ephemeral and capacity-limited. Repeat to different paths with `--mode redacted` if needed. For staging replace the Compose prefix with `docker compose --env-file .env.azure -p mirage-staging -f compose.azure-staging.yml`. Do not expose the database publicly for exports. Session-attached provenance overrides environment labels; do not relabel old evidence as new source.

To attach the console to an existing manual stack without managing services, set its original `POSTGRES_PASSWORD`, `POSTGRES_HOST=127.0.0.1`, `POSTGRES_PORT=5433` and an authenticated `REDIS_URL` for port 6379 (URL-encode password special characters), then:

```bash
CHRONOS_MANAGE_STACK=0 cargo run --locked --manifest-path src/chronos/dashboard/Cargo.toml
```

Connect-only mode does not start/stop services. Use the explicit CLI export route for this mode; do not assume managed-container export transfer or remote Azure administration. The historical over-100-session walkthrough does not substitute for a new visual GUI check.

## Stop and preserve evidence

Use `docker compose down` to stop services while retaining named volumes. `make clean` runs `docker compose down -v` and deletes Compose volumes; use it only for explicitly disposable deployments. Before any destructive recovery/load test, verify the exact container, network and volume names.

Troubleshooting and release validation belong in [VERIFICATION_PLAN.md](VERIFICATION_PLAN.md). Record source/patch identity, selected Compose files, environment, commands and observed results.

### Backup and recovery boundary

Before backing up, stop admission, disconnect participants, wait for audit delivery, export important sessions, and stop writers. Inventory the exact project volumes. Preserve PostgreSQL, Redis, audit spool, credentials, profile/config and source/image identities together. PostgreSQL alone omits pending events and filesystem state. Restore into a separate disposable project and verify authentication, marker files, persona, audit reconciliation and exports before trusting the backup. A full backup/restore drill is **not a completed gate**; do not delete original volumes or the VM based on this checklist. Redis AOF every-second syncing is not zero-loss durability.

### Troubleshooting

| Symptom | Safe check/action |
|---|---|
| Docker socket missing | Start Docker; wait for `docker info`. Permission denied is distinct from a stopped daemon. |
| Missing credentials | Load original credentials and run `config --quiet`; never share rendered config. |
| Port occupied | Identify the owner; stop only your conflicting lab or change the tunnel's local port. |
| Database authentication after restart | Match saved credentials to volumes; environment changes do not rotate the stored password. |
| FUSE/confinement failure | Check `/dev/fuse` and required capabilities; do not disable containment to obtain a pass. |
| SSH unreachable on Docker Desktop | Check readiness and bindings; prefer managed relay, not an internet-connected research network. |
| Host-key changed | Verify the intended instance fingerprint before replacing only that endpoint's known-host entry. |
| Unexpected disconnect | Check idle/command/CPU/lease limits, host suspension and dependency logs; record interruption. |
| Resume absent/wrong | Check paused status, expiry, competing connection and profile revision. |
| Live Ops stale / audit pending | Inspect dependencies and spool delivery; missing rows are not proof of no activity. |
| Export incomplete | Check UUID, credentials, DB port, space and new destination; retain partial output separately. |
| Prepared initialization fails | Verify bundle/profile/model identities; reprepare or deliberately use deterministic fresh runs. |
| Disk full / Redis rejects writes | Stop admission and inspect retention; do not flush state or enable eviction as an undocumented fix. |

See [test instructions](../tests/README.md) and the [current coverage review](WORKING_REVIEW_2026-10-22.md). Never aim disruptive checks at valuable operator volumes. A finite suite cannot establish safety against every possible attack or failure.
