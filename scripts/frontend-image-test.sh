#!/usr/bin/env bash
# Test for the frontend image (frontend/Dockerfile + nginx template): it must start without
# a backend (Aiven Runtime deploys it on its own), proxy /api to BACKEND_URL, and keep
# reaching the backend after that container is recreated with a new IP (#64).
# Needs Docker. Usage: scripts/frontend-image-test.sh   (run by CI's containers job)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
id="bobtest-$$"
net="$id-net"
image="$id-frontend"
cleanup() {
  docker rm -f "$id-web" "$id-api1" "$id-api2" "$id-filler" >/dev/null 2>&1 || true
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

port() { docker port "$1" 80/tcp | head -1 | sed 's/.*://'; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1" || true; }
body() { curl -s --max-time 5 "$1" || true; }
running() { docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || echo false; }
ip() { docker inspect -f "{{(index .NetworkSettings.Networks \"$net\").IPAddress}}" "$1"; }

# fake_api <name> <text>: an nginx container answering /api/health with <text>, as "fakeapi"
fake_api() {
  docker run -d --name "$1" --network "$net" --network-alias fakeapi nginx:1.29-alpine \
    sh -c "mkdir -p /usr/share/nginx/html/api && echo '$2' >/usr/share/nginx/html/api/health && exec nginx -g 'daemon off;'" >/dev/null
}

docker build -q -t "$image" "$here/../frontend" >/dev/null
docker network create "$net" >/dev/null

# 1. No backend at all: nginx starts and stays up, serves the UI, and /api is a 502.
docker run -d --name "$id-web" --network "$net" -p 127.0.0.1::80 "$image" >/dev/null
sleep 4
web="http://127.0.0.1:$(port "$id-web")"
check "starts without a backend" true "$(running "$id-web")"
check "serves the UI page" 1 "$(body "$web/" | grep -c '<title>bobBuilder</title>')"
check "/api without a backend is 502" 502 "$(code "$web/api/health")"
docker rm -f "$id-web" >/dev/null

# 2. BACKEND_URL names the backend: /api goes there, with the path unchanged.
fake_api "$id-api1" first
docker run -d --name "$id-web" --network "$net" -p 127.0.0.1::80 \
  -e BACKEND_URL=http://fakeapi:80 "$image" >/dev/null
sleep 4
web="http://127.0.0.1:$(port "$id-web")"
check "proxies /api to BACKEND_URL" first "$(body "$web/api/health")"

# 3. The backend is recreated with a new IP: nginx follows it without a restart (#64).
old_ip="$(ip "$id-api1")"
docker rm -f "$id-api1" >/dev/null
docker run -d --name "$id-filler" --network "$net" nginx:1.29-alpine >/dev/null # takes the freed IP
fake_api "$id-api2" second
check "recreated backend has a new IP (test setup)" true "$([[ "$(ip "$id-api2")" != "$old_ip" ]] && echo true || echo false)"
sleep 11 # resolver cache is valid=10s
check "follows a recreated backend" second "$(body "$web/api/health")"
exit $status
