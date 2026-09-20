#!/usr/bin/env bash
# Owns only uniquely named disposable resources. Does not touch the Compose stack.
set -euo pipefail
cd "$(dirname "$0")/../.."
test_prefix="apate-integration-$$"
test_image="apate-integration:$$"
cleanup() {
  docker rm -fv "$test_prefix-core" "$test_prefix-redis" "$test_prefix-pg" >/dev/null 2>&1 || :
  docker network rm "$test_prefix-net" >/dev/null 2>&1 || :
}
trap cleanup EXIT
docker build -q -t "$test_image" .
docker network create --internal "$test_prefix-net"
docker run -d --name "$test_prefix-redis" --network "$test_prefix-net" redis:7-alpine redis-server --save '' --appendonly no
docker run -d --name "$test_prefix-pg" --network "$test_prefix-net" -e POSTGRES_USER=chronos -e POSTGRES_PASSWORD=chronos_dev_password -e POSTGRES_DB=chronos postgres:15-alpine
test_ready=false
for ((attempt=0; attempt<60; attempt++)); do
  if docker exec "$test_prefix-pg" pg_isready -U chronos >/dev/null 2>&1; then
    test_ready=true
    break
  fi
  sleep 1
done
"$test_ready"
docker run --rm -v "$PWD/tests:/app/tests:ro" "$test_image" python3 tests/integration/verify_containment.py
docker run --rm --network "$test_prefix-net" -e POSTGRES_HOST="$test_prefix-pg" -v "$PWD/tests:/app/tests:ro" "$test_image" python3 tests/integration/verify_audit_recovery.py
docker run --rm --name "$test_prefix-core" --network "$test_prefix-net" \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --tmpfs /var/lib/chronos:rw,nosuid,size=128m --tmpfs /mnt/honeypot:rw,nosuid,size=1m \
  --cap-drop ALL --cap-add SYS_ADMIN --cap-add SYS_CHROOT --cap-add SETUID --cap-add SETGID --cap-add KILL \
  --device /dev/fuse --security-opt apparmor=unconfined --security-opt no-new-privileges:true \
  --pids-limit 192 --memory 2g --cpus 2 \
  -e REDIS_HOST="$test_prefix-redis" -e POSTGRES_HOST="$test_prefix-pg" -e CHRONOS_TEST_AUDIT=1 \
  -v "$PWD/tests:/app/tests:ro" "$test_image" python3 tests/integration/verify_linux_ssh.py
