# Mirage private research operations

Use this runbook with [HOW_TO.md](HOW_TO.md) and [AZURE_STAGING.md](AZURE_STAGING.md). All commands assume the repository root and the exact Compose project/files used at startup. The desktop supervisor must be closed before manually operating its containers. Keep participant access paused throughout backup and restore.

## Cold backup procedure

1. Record source/configuration identity and `docker inspect` image IDs/digests for all three services. Save profile/configuration and the original Redis/PostgreSQL credentials privately. Physical database copies must restore using the same image/platform and database major version; upgrades require a separate migration.
2. Close admission at the private tunnel/administrator access layer. Disconnect participants. Wait for runs to pause, session evidence to finalize and audit delivery to drain. Export important sessions. If delivery cannot drain, preserve the SQLite outbox and record that condition rather than discarding it.
3. Stop the core first, then stop Redis and PostgreSQL using the original Compose prefix. Confirm every writer has stopped. Do not take sequential filesystem copies while services continue writing: those copies can describe different points in time.
4. Inspect the stopped service mounts and record the exact named volumes. Preserve **redis-data, postgres-data and audit-spool together**. The FUSE mount is reconstructed at startup; do not restore a live mount. The audit-spool volume also retains the SSH host key.
5. Create a new private backup directory under ignored `backups/` with mode 0700. Copy each stopped volume to a separate tar archive through a read-only helper mount. Use the reviewed core image as the helper, no network, no Docker socket mount. A command template for one already resolved volume is:

   ```sh
   umask 077
   docker run --rm --network none -v EXACT_SOURCE_VOLUME:/volume:ro \
     EXACT_REVIEWED_CORE_IMAGE tar -cpf - -C /volume . > backups/NEW_BACKUP/VOLUME.tar
   shasum -a 256 backups/NEW_BACKUP/VOLUME.tar
   ```

   Replace placeholders explicitly. Create the new parent directory first; never overwrite an earlier backup. Save archive hashes, byte sizes, stopped-state/image inventory and credentials alongside the backup using private permissions. Tar archives contain participant data and keys; keep them on protected storage. A hash alone does not encrypt data or establish authenticity.
6. Restart the original services with their original credentials and perform a health check if the experiment is continuing. Retain the original volumes until a separate restoration has passed. Record the downtime interval.

## Restore into a separate deployment

1. Verify backup hashes against the trusted manifest before extraction. Accept only your trusted backups; arbitrary tar input can contain unsafe paths. Retrieve the recorded image digests and configuration and load the saved credentials privately.
2. Choose a new project and empty volumes. Keep the original project stopped if both would publish port 2222. Run the matching Compose `create --pull never` to allocate resources without starting writers. Confirm the destination volume names belong to the new project.
3. Restore each archive to its corresponding **empty** named volume using `docker run --rm -i --network none -v EXACT_NEW_VOLUME:/volume EXACT_REVIEWED_CORE_IMAGE tar -xpf - -C /volume < EXACT_ARCHIVE`. Preserve ownership/modes. Do not merge files into an initialized database or original volume. Never attach old and new writers to the same data volume.
4. Start the restored graph with its original credentials. Verify Redis rejects unauthenticated requests, PostgreSQL accepts the saved password, core/FUSE/SSH become ready, and the SSH host-key fingerprint matches the backup.
5. Compare persona/device facts, paused run IDs, marker file bytes and saved cwd. Resume one controlled paused run and verify it through interactive SSH. Confirm a fresh run remains isolated.
6. Reconcile previously committed audit event IDs and session history. Any pending outbox event must reach PostgreSQL once after restart. Generate raw and redacted exports and verify every `complete.json` hash. Test important sessions, not just the existence of database files.
7. Record outcome, image identities, backup hashes and remaining discrepancies before deciding whether to retire the original system. A successful synthetic drill verifies the procedure on its tested configuration; repeat with the actual Azure storage and recovery process.

## Reproduce the disposable readiness drill

This harness creates unique source/restore projects and bounded pressure containers. It deletes only its disposable volumes on exit and retains private backups/results. It needs Docker/FUSE, the three local images and a free loopback port 2222:

```sh
python3 tests/integration/verify_operational_readiness.py \
  --core mirage-gate:20261019 \
  --redis mirage-redis-gate:20261019-nonroot \
  --postgres mirage-postgres-gate:20261019 \
  --output evidence/operations_NEW_RUN
```

Use a new output path. These are local candidate tags; substitute the reviewed image IDs/digests for your build. The output is ignored by Git and contains **credentials and physical backups**. Do not force-add the directory. Keep a sanitized result summary in documentation.

The drill creates an SSH marker and paused run, snapshots all three stopped volumes, restores them under a new project, replays a pending audit event, resumes the run and verifies export hashes. It also fills a dedicated 4 MiB tmpfs to real `ENOSPC`, checks that SQLite rejects a new event while preserving the previous one, releases pressure and checks recovery. A separate Redis instance uses an 8 MiB no-eviction limit to verify write rejection, retention of an acknowledged key and successful writes after pressure is removed. These faults do not fill the host disk or alter operator databases.

## Incident stop and storage response

Stop participant admission first. Preserve the first failure timestamp and service logs. For disk or Redis capacity errors, stop writes, check free space and retention, and preserve the database/outbox before changing limits. Do not enable eviction, flush Redis, delete the outbox or rotate credentials as a capacity workaround. After freeing space, verify database integrity, audit delivery, history and exports before reopening access.

A full host-disk outage, PostgreSQL disk exhaustion, sudden host power loss, encrypted off-host backup transport and multi-day retention remain separate acceptance cases. Bounded tmpfs and Redis faults do not establish those behaviors.

## Desktop and Azure handoff

Desktop acceptance follows launch, automatic readiness, two isolated SSH sessions, visible Live Ops, disconnect/finalization, GUI-selected resume/fresh, both exports, quit and relaunch. Preserve native credentials and research volumes. See the dated readiness report for what was actually observed.

On Azure verify architecture, kernel FUSE support, exact image digests, private NSG/tunnel behavior, required authentication, host storage alerts, recovery and backup destination. Configure an operator-owned budget alert before leaving the VM running. Rebuilding/publishing images and creating cloud resources are separate deployment actions; local readiness does not establish real Azure behavior.
