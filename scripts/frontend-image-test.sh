#!/usr/bin/env bash
# Test for the frontend image (frontend/Dockerfile + nginx template): it must start without
# a backend (Aiven Runtime deploys it on its own), proxy /api to BACKEND_URL, keep reaching
# the backend after that container is recreated with a new IP (#64), and refuse to start,
# saying why, when BACKEND_URL has a path or the container has no DNS server.
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

port() { docker port "$1" 80/tcp 2>/dev/null | head -1 | sed 's/.*://' || true; } # empty once stopped
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1" || true; }
body() { curl -s --max-time 5 "$1" || true; }
running() { docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || echo false; }
ip() { docker inspect -f "{{(index .NetworkSettings.Networks \"$net\").IPAddress}}" "$1"; }

# web [docker run options...]: (re)starts the image as $id-web; prints its URL once nginx
# answers, or nothing if the container stops first (up to 15 s)
web() {
  docker rm -f "$id-web" >/dev/null 2>&1 || true
  docker run -d --name "$id-web" --network "$net" -p 127.0.0.1::80 "$@" "$image" >/dev/null
  for _ in $(seq 30); do
    [[ "$(running "$id-web")" == true ]] || return 0
    local p url
    p="$(port "$id-web")"
    url="http://127.0.0.1:$p"
    [[ -n "$p" && "$(code "$url/")" != 000 ]] && {
      echo "$url"
      return 0
    }
    sleep 0.5
  done
}

# fake_api <name> <text>: an nginx container answering /api/health with <text>, as "fakeapi"
fake_api() {
  docker run -d --name "$1" --network "$net" --network-alias fakeapi nginx:1.29-alpine \
    sh -c "mkdir -p /usr/share/nginx/html/api && echo '$2' >/usr/share/nginx/html/api/health && exec nginx -g 'daemon off;'" >/dev/null
}

docker build -q -t "$image" "$here/../frontend" >/dev/null
docker network create "$net" >/dev/null

# 1. No backend at all: nginx starts and stays up, serves the UI, and /api is a 502.
url="$(web)"
check "starts without a backend" true "$(running "$id-web")"
check "serves the UI page" 1 "$(body "$url/" | grep -c '<title>AskBob</title>')"
check "/api without a backend is 502" 502 "$(code "$url/api/health")"

# 2. BACKEND_URL names the backend: /api goes there, with the path unchanged.
fake_api "$id-api1" first
url="$(web -e BACKEND_URL=http://fakeapi:80)"
check "proxies /api to BACKEND_URL" first "$(body "$url/api/health")"

# 3. The backend is recreated with a new IP: nginx follows it without a restart (#64).
old_ip="$(ip "$id-api1")"
docker rm -f "$id-api1" >/dev/null
docker run -d --name "$id-filler" --network "$net" nginx:1.29-alpine >/dev/null # takes the freed IP
fake_api "$id-api2" second
check "recreated backend has a new IP (test setup)" true "$([[ "$(ip "$id-api2")" != "$old_ip" ]] && echo true || echo false)"
sleep 11 # resolver cache is valid=10s
check "follows a recreated backend" second "$(body "$url/api/health")"

# 4. A trailing slash is dropped, so the request path still reaches the backend.
url="$(web -e BACKEND_URL=http://fakeapi:80/)"
check "BACKEND_URL with a trailing slash still proxies" second "$(body "$url/api/health")"

# 5. A path in BACKEND_URL would replace every request path: refuse to start and say why.
web -e BACKEND_URL=http://fakeapi:80/base >/dev/null
check "BACKEND_URL with a path stops the container" false "$(running "$id-web")"
check "... and says why" 1 "$(docker logs "$id-web" 2>&1 | grep -c 'BACKEND_URL must be')"

# 6. No nameserver in /etc/resolv.conf: refuse to start and say why. Docker always writes
# one, so empty the file and then run the image's normal entrypoint.
docker rm -f "$id-web" >/dev/null 2>&1 || true
docker run -d --name "$id-web" --entrypoint sh "$image" \
  -c 'echo "# no nameserver" >/etc/resolv.conf && exec /docker-entrypoint.sh nginx -g "daemon off;"' >/dev/null
for _ in $(seq 20); do [[ "$(running "$id-web")" == false ]] && break; sleep 0.5; done
check "no DNS server stops the container" false "$(running "$id-web")"
check "... and says why" 1 "$(docker logs "$id-web" 2>&1 | grep -c 'no nameserver')"
exit $status
