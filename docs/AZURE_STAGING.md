# Azure private staging and release gates

Mirage Research has completed its predeployment gates for private authorized ARM64 testing, not unrestricted public attacker access. On October 19 the checkout passed 272 Python tests with seven skips, 13 Rust tests with one opt-in integration test ignored, Linux integration, an authenticated 3,600-second soak and actual standalone staging startup. The operator accepted documented residual core risks for a disposable private VM only. See the [gate verdict](RELEASE_EVIDENCE_INDEX_2026-10-19.md) and [security review](DEPLOYMENT_SECURITY_REVIEW_2026-10-19.md). Repeat host-dependent smoke checks after provisioning.

## Hosting and isolation

Use a dedicated disposable Linux VM with Docker Engine and `/dev/fuse` for initial staging. This is an engineering recommendation based on the current FUSE and capability requirements. Azure Container Instances does not support privileged container operations ([Microsoft documentation](https://learn.microsoft.com/en-us/azure/container-instances/container-instances-troubleshooting#cant-connect-to-underlying-docker-api-or-run-privileged-containers)). Do not assume the macOS desktop application is a remote Azure control plane.

Start with 4 vCPU and 8 GiB RAM as a provisional staging budget, not a measured capacity guarantee. The stack caps core memory at 2 GiB, Redis at 1.5 GiB and PostgreSQL at 1 GiB; leave capacity for the host and testing. Use a separate resource group, no production peering or credentials, and no attached managed identity. Keep application containers on the internal Docker network; do not mount the Docker socket or host home directory.

Keep port 2222 loopback-only. Reach it through an authenticated administrator SSH tunnel or a private network. Allow management SSH only through approved administrator sources or [Azure Bastion](https://learn.microsoft.com/en-us/azure/bastion/bastion-connect-vm-ssh-linux). Define explicit [NSG rules](https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview) rather than assuming a subnet isolates the VM. Container containment is not a guarantee against host escape: the trusted core retains SYS_ADMIN and an unconfined AppArmor profile for FUSE. Do not place valuable workloads on this VM.

## Prepare and start

1. Build all three images from the exact reviewed source for ARM64, scan them and publish them to your registry. Use `Dockerfile` for core, `Dockerfile.redis` for Redis and `Dockerfile.postgres` for PostgreSQL. Record the source manifest, platform and registry digests. PostgreSQL runs as `postgres` without gosu; use named volumes, not root-owned bind mounts. Updated Alpine package repositories are build inputs, so a future rebuild needs its own scan. Resolve the core scan's high-severity findings before broader exposure, or explicitly review and accept their scoped residual risk.
2. Create a private `.env.azure` file with mode 0600 containing independent random `REDIS_PASSWORD` and `POSTGRES_PASSWORD`, plus `MIRAGE_IMAGE`, `MIRAGE_REDIS_IMAGE` and `MIRAGE_POSTGRES_IMAGE`, each set to its actual `registry/repository@sha256:...` published digest. Never commit or print these credentials. Environment variables are visible to host/Docker administrators; this is not a secret vault. Retain credentials securely: changing the PostgreSQL variable does not rotate an initialized database password.
3. From the repository on the VM, validate then start only this standalone stack:

   ```sh
   docker compose --env-file .env.azure -p mirage-staging -f compose.azure-staging.yml config --quiet
   docker compose --env-file .env.azure -p mirage-staging -f compose.azure-staging.yml up -d
   docker compose --env-file .env.azure -p mirage-staging -f compose.azure-staging.yml ps
   ```

   This configuration has no source bind mounts, database host ports, optional inference, monitoring, or experimental services. Do not merge it with `docker-compose.yml`. The digest must be supplied by the operator; YAML interpolation does not validate digest syntax.
4. Tunnel the research port from your workstation using your real VM administrator and approved host:

   ```sh
   ssh -N -L 2222:127.0.0.1:2222 ADMIN@VM
   # In a second terminal, connect to the fake system, not the VM admin shell:
   ssh -p 2222 ubuntu@127.0.0.1
   ```

   Use an unused local port if the desktop lab already occupies 2222. Verify host keys through your approved process; do not disable host-key checks.

## Acceptance before broader access

- Verify image/source identity, Redis rejects unauthenticated commands, and PostgreSQL requires credentials. Confirm no database, monitoring or model endpoint is reachable from outside the VM.
- Run Linux/FUSE isolation, SSH forwarding/exec denial, overflow handling, persona persistence, fresh-run isolation, audit reconciliation, restart/recovery and export integrity checks on the actual architecture. Seven skipped Python checks are not deployment passes.
- The pinned local ARM64 candidate passed the authenticated persistent eight-client 3,600-second workload. Repeat it for a rebuilt image or materially different runtime configuration, recording source identity, sample gaps, memory, command reconciliation and retained-run state. Keep Docker running and the host awake; do not increase ownership TTL to hide sleep failures. See `tests/integration/run_load.py` and `docs/PERSISTENT_CAPACITY_2026-10-16.md` for workload identity and earlier results.
- Test backup and restoration of PostgreSQL, Redis and the audit spool together in a disposable stack. Redis AOF every-second syncing is not zero-loss durability. Establish evidence retention, free-disk alerts, incident stop procedures and an Azure budget alert before leaving it running. Budget alerts are not a spending cap.
- Freeze the final changed source and image again after fixes. Record results against that exact identity. Public exposure requires a separate threat/risk review and explicit authorization; this staging configuration intentionally does not enable it.

Stop with the same Compose prefix and `stop`; use `down` only when ready to remove this stack's containers. Never add `-v` unless intentionally deleting the research data. Preserve/export evidence before VM deletion. Home deployment and model training remain separate workstreams, not requirements silently satisfied by this stack.
