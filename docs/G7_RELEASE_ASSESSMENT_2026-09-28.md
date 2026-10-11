# G7 release assessment — 2026-09-28

## Decision

**G7 is partially verified, not passed.** A no-cache image build and isolated Linux/FUSE runtime exercise passed, the native console walkthrough and language dependency audits exist, and disposable resources were cleaned. The source candidate is now frozen with a manifest, tracked patch, resolved image inventory and extracted-copy verification. The release criterion still lacks an authorized container/OS CVE result.

## Frozen candidate identity

- Git base: `a098fe02771802de03b9c64c8fbce52d82defc38`; working tree dirty with 72 changed/untracked paths at assessment time.
- Release `src/` + `config/` tree digest: `32a7be6a9caed227ea90c7b115b52046ef19977d9842e9200796b7eba22e3068` across 79 files. The digest construction hashes each sorted relative path and its SHA-256; it excludes bytecode, `__pycache__` and Rust `target` files.
- Dockerfile: `429a8e15f0d367d72cbed2eef737f6805b7e3ab52311edcb6b57d2d42054c22d`.
- Requirements: `730a7013b2f814d0755654e6f7b0c51c612e3f67125124e19fdcaf8d81daf68d`.
- Compose: `3380dd8907f689b45b8dc5f49c560e14fc5863a2ebb5ad20bd627639429ca1f0`.
- Ubuntu profile: `302ffe87796fbacaf0d2decafde18b31e278862ee86764bac1351a6d0d5adda3`.
- Generation policy: `9b967552d8349df4c4bb811831089d68418a13cdf99493b2d6e165ca57b24539`.

This preliminary identity was superseded by the complete frozen bundle in `evidence/release_candidate_20260928/`. Its authoritative archive and manifest hashes are listed in [RELEASE_EVIDENCE_INDEX_2026-09-28.md](RELEASE_EVIDENCE_INDEX_2026-09-28.md). A cryptographic signature is optional for this college-project scope.

## Procedures and results

1. `docker build --no-cache -t apate-g7-fresh:20260928 .` passed using Docker Engine 29.8.0 on arm64 Docker Desktop. It fetched current Debian Trixie package metadata and reinstalled Python dependencies from the pinned Python base-image digest.
2. The resulting local manifest-list identity was `sha256:3bd7d0ce06037cb820b34b161e2562c52522956f76c84ee3ddc4225fa814a1a1`; reported image size was 372,013,800 bytes. The image was deleted after assessment and can be rebuilt.
3. A disposable smoke container imported the simulation orchestrator and loaded the `web01` profile successfully.
4. `bash tests/integration/run_linux.sh` passed using uniquely named Redis, PostgreSQL, core and network resources. It verified restricted-worker containment; database-outage retention; uncertain-commit deduplication; real SSH/FUSE isolation and permissions; non-model deterministic generation; forced-worker interruption while another session survived; and PostgreSQL export/event correlation. Injected database errors in its output were expected fault stimuli.
5. Base Compose configuration rendered successfully. Its service set was `db-store`, `redis-store`, `core-engine`; adding the inference profile added `ollama`. Placeholder secrets were used only for configuration rendering and were not retained.
6. The earlier connected native-console walkthrough passed its frozen G4 procedure on this working-tree series. It was not rebuilt from the disposable Linux image because the console is a separate native Rust application.
7. The image contained 91 Debian packages and 26 Python distributions. Pip/setuptools/wheel and APT index files were removed. The largest project-added layers were approximately 66.5 MB for Python dependencies and 47.3 MB for OS upgrade/FUSE dependencies. The application/config copy was under 1 MB.
8. The image starts as root because the core mounts FUSE and constructs a chroot before dropping restricted workers. Standard Debian setuid utilities remain present. The supported Compose boundary mitigates this with a read-only root, `cap_drop: ALL`, an explicit capability allowlist, `no-new-privileges`, PID/memory/CPU limits and loopback-only published ports. Direct unconfined image execution is not the supported deployment.
9. Twelve unused historical `apate-integration:*` image tags, each with zero referencing containers, plus this run's image were removed. The harness now deletes its own uniquely tagged image on exit. No retained Mirage containers, networks, volumes or evidence were modified.

## Candidate-freeze follow-up

After the command-contract correction, the candidate was rebuilt without cache, inventoried and re-frozen as a deterministic 158-file archive. The extracted archive passed the complete default Python suite (132 passed, 7 skipped), dashboard formatting and four locked Rust tests. The current inventory records 91 Debian packages and 26 Python distributions. See the release evidence index for hashes and scope.

## Why the gate remains open

- Docker Scout 1.24.0 was available, but its CVE analysis requires Docker's external vulnerability service and would transmit image/package metadata. That transmission was not authorized, so no container-CVE count is claimed.
- `requirements.txt` pins direct Python dependencies but not every transitive artifact hash, and `apt-get update && apt-get upgrade` resolves mutable repository state. The exact packages in this candidate are now recorded, but the inputs do not guarantee a future bit-identical rebuild. Bit-identical rebuilds are not an MVP requirement.
- The no-cache build and Linux run establish the documented arm64 Docker Desktop environment. Repetition on another clean Linux host would strengthen portability evidence but is not a mandatory gate by itself.
- The console walkthrough and fresh container build are complementary evidence, not one monolithic packaged installer.

## Required closure work

1. Run an authorized local/offline scanner or explicitly approve the Docker Scout metadata disclosure; record database timestamp, severities, fixes and dispositions.
2. Re-freeze and reverify if the candidate changes. Hash-locking or Debian snapshots may be added for stronger supply-chain reproducibility; the MVP does not claim bit-identical rebuilds.
3. A second-host repetition is recommended stronger evidence when available, not a mandatory gate.
