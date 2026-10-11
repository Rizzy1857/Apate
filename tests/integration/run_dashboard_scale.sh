#!/usr/bin/env bash
# Owns uniquely named disposable PostgreSQL/network resources.
set -euo pipefail
cd "$(dirname "$0")/../.."
test_prefix="apate-dashboard-scale-$$"
test_image="apate-dashboard-scale:$$"
cleanup() {
  docker rm -fv "$test_prefix-pg" >/dev/null 2>&1 || :
  docker network rm "$test_prefix-net" >/dev/null 2>&1 || :
}
trap cleanup EXIT
docker build -q -t "$test_image" .
docker network create --internal "$test_prefix-net" >/dev/null
docker run -d --name "$test_prefix-pg" --network "$test_prefix-net" \
  -e POSTGRES_USER=chronos -e POSTGRES_PASSWORD=chronos_dev_password \
  -e POSTGRES_DB=chronos postgres:15-alpine >/dev/null
for ((attempt=0; attempt<60; attempt++)); do
  if docker exec "$test_prefix-pg" pg_isready -U chronos >/dev/null 2>&1; then
    docker run --rm --network "$test_prefix-net" \
      -e POSTGRES_HOST="$test_prefix-pg" -v "$PWD/tests:/app/tests:ro" \
      "$test_image" python3 tests/integration/verify_dashboard_scale.py
    exit
  fi
  sleep 1
done
echo "Disposable PostgreSQL did not become ready" >&2
exit 1
