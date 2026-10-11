# Mirage operator guide — current limitations

Reviewed 2026-09-27. Mirage Research is not release-ready. This guide supports controlled local development; it does not authorize public exposure.

## Preflight

Use a supported Linux Docker host with FUSE for the full path. Review both `docker-compose.yml` and any local override. Define `POSTGRES_PASSWORD` and, because current Compose interpolates it even for the optional monitoring profile, `GRAFANA_PASSWORD`. Base Compose is the deterministic no-model treatment; Ollama is optional.

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

Prepared artifacts are a separate, explicit treatment. First run the preparation command against the chosen Ollama service, then start fresh session namespaces with both the existing bundle and:

```bash
docker compose -f docker-compose.yml --profile inference up -d redis-store db-store ollama
docker compose -f docker-compose.yml --profile inference exec ollama ollama pull llama3.2:3b
docker compose -f docker-compose.yml --profile inference exec ollama ollama pull llama3:8b
docker compose -f docker-compose.yml --profile inference run --rm \
  -e OLLAMA_HOST=ollama core-engine \
  python3 -m chronos.intelligence.prepared_artifacts
CHRONOS_ARTIFACT_TREATMENT=prepared docker compose -f docker-compose.yml up --build -d
```

Record the exact model digests after pulling them. The default is `CHRONOS_ARTIFACT_TREATMENT=deterministic`, which never loads a stored prepared bundle. Selecting `prepared` without a complete current bundle fails before filesystem initialization. Changing the treatment does not replace files in an already initialized session namespace.

Do not infer readiness from a running container alone. Confirm Redis/PostgreSQL health, a mounted FUSE path, the SSH listener, the audit worker, and absence of repeated delivery errors.

## Controlled SSH session

Connect to the configured local endpoint (base Compose publishes loopback port 2222; a local override may proxy it differently):

```bash
ssh -p 2222 ubuntu@127.0.0.1
```

Inspect and accept the expected development host-key fingerprint rather than globally disabling host-key checking. The explicit deception policy accepts the claimed password/public-key username as an observation while using the configured profile identity inside the emulator. Evidence records claimed and effective identities separately. This is not a production authentication design, and passwords are never recorded.

Use only the versioned surface in [COMMAND_CONTRACT_V1.md](COMMAND_CONTRACT_V1.md). The bounded G1 contract passed both its reference matrix and real SSH/FUSE reconciliation. Do not use a direct `docker exec` shell as evidence of an attributed participant session; PID-based session registration is part of the supported SSH path.

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

Run the native console separately with its database environment configured:

```bash
cargo run --manifest-path src/chronos/dashboard/Cargo.toml
```

Use the console for development inspection, not a general completeness claim. The frozen over-100-session G4 walkthrough passed on 2026-09-27; repeat it for a release candidate when UI, schema or deployment inputs change materially.

## Stop and preserve evidence

Use `docker compose down` to stop services while retaining named volumes. `make clean` runs `docker compose down -v` and deletes Compose volumes; use it only for explicitly disposable deployments. Before any destructive recovery/load test, verify the exact container, network and volume names.

Troubleshooting and release validation belong in [VERIFICATION_PLAN.md](VERIFICATION_PLAN.md). Record source/patch identity, selected Compose files, environment, commands and observed results.
