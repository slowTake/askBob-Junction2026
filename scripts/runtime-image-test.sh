#!/usr/bin/env bash
# Test for the single-container image (deploy/runtime/, D-034): nginx, the API and the
# ingest worker in one container, as deployed to Aiven Runtime. Runs it against throwaway
# Postgres and Valkey containers and checks it from the outside through its one port.
# Needs Docker. Usage: scripts/runtime-image-test.sh   (run by CI's containers job)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$here/.."
id="bobrt-$$"
net="$id-net"
image="$id-image"
cleanup() {
  docker rm -f "$id-app" "$id-pg" "$id-valkey" >/dev/null 2>&1 || true
  docker network rm "$net" >/dev/null 2>&1 || true
  docker image rm "$image" >/dev/null 2>&1 || true
}
trap cleanup EXIT

status=0
check() { # $1 = name, $2 = expected, $3 = actual
  if [[ "$2" == "$3" ]]; then
    echo "ok: $1"
  else
    echo "FAIL: $1: expected '$2', got '$3'"
    status=1
  fi
}
running() { docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || echo false; }

docker build -q -f "$root/deploy/runtime/Dockerfile" -t "$image" "$root" >/dev/null
docker network create "$net" >/dev/null
docker run -d --name "$id-pg" --network "$net" --network-alias pg \
  -e POSTGRES_USER=bob -e POSTGRES_PASSWORD=bob -e POSTGRES_DB=bob pgvector/pgvector:pg17 >/dev/null
docker run -d --name "$id-valkey" --network "$net" --network-alias valkey valkey/valkey:8-alpine >/dev/null
for _ in $(seq 60); do
  docker exec "$id-pg" pg_isready -U bob -d bob >/dev/null 2>&1 && break
  sleep 1
done

# The app as Runtime runs it: one container, one published HTTP port (8080), secrets as env.
docker run -d --name "$id-app" --network "$net" -p 127.0.0.1::8080 \
  -e DATABASE_URL=postgresql://bob:bob@pg:5432/bob -e VALKEY_URL=redis://valkey:6379/0 \
  "$image" >/dev/null
url="http://127.0.0.1:$(docker port "$id-app" 8080/tcp | head -1 | sed 's/.*://')"

# 1. Everything answers through the one port: API healthy, worker listening, UI served.
smoke_code=0
API_URL="$url" WEB_URL="$url" SMOKE_TIMEOUT=120 "$here/smoke.sh" || smoke_code=$?
check "smoke passes through the single port" 0 "$smoke_code"

# 2. Server-sent events stream through nginx (the first line arrives at once).
check "SSE streams" ": connected" "$(curl -sN --max-time 3 "$url/api/events" 2>/dev/null | head -1 || true)"

# 3. It does not run as root.
check "runs as a non-root user" false "$([[ "$(docker exec "$id-app" id -u)" == 0 ]] && echo true || echo false)"

# 4. If one process dies (here the worker), the container stops so Runtime restarts it.
docker exec "$id-app" pkill -f 'python -m app.worker' || true
for _ in $(seq 20); do [[ "$(running "$id-app")" == false ]] && break; sleep 0.5; done
check "container stops when the worker dies" false "$(running "$id-app")"
[[ $status == 0 ]] || docker logs "$id-app" 2>&1 | tail -30
exit $status
