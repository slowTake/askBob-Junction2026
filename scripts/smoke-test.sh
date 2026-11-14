#!/usr/bin/env bash
# Test for scripts/smoke.sh against small local HTTP servers standing in for the API
# (:8000) and the UI (:8080). Usage: scripts/smoke-test.sh   (run by `make check`)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp -d)"
: >"$tmp/pids" # serve runs in $(...), a subshell, so PIDs go to a file, not an array
cleanup() {
  while read -r p; do kill "$p" 2>/dev/null || true; done <"$tmp/pids"
  rm -rf "$tmp"
}
trap cleanup EXIT

free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }

# serve <dir>: serves a directory, prints its base URL once it answers
serve() {
  local port
  port="$(free_port)"
  python3 -m http.server "$port" --bind 127.0.0.1 --directory "$1" >/dev/null 2>&1 &
  echo $! >>"$tmp/pids"
  for _ in $(seq 50); do
    curl -s -o /dev/null "http://127.0.0.1:$port/" && break
    sleep 0.1
  done
  echo "http://127.0.0.1:$port"
}

# site <name> <health json> [ui]: a directory with api/health and, if "ui", index.html
site() {
  mkdir -p "$tmp/$1/api"
  printf '%s' "$2" >"$tmp/$1/api/health"
  if [[ "${3:-}" == ui ]]; then printf '<!doctype html><title>AskBob</title>' >"$tmp/$1/index.html"; fi
}

healthy='{"ok":true,"data":{"postgres":true,"valkey":true,"ingest_workers":1},"error":null}'
no_worker='{"ok":true,"data":{"postgres":true,"valkey":true,"ingest_workers":0},"error":null}'
site good "$healthy" ui
site nodb '{"ok":false,"data":{"postgres":false,"valkey":true,"ingest_workers":1},"error":null}' ui
site noworker "$no_worker" ui
site nocount '{"ok":true,"data":{"postgres":true,"valkey":true},"error":null}' ui
site late "$no_worker" ui
site noui "$healthy"
good="$(serve "$tmp/good")"
nodb="$(serve "$tmp/nodb")"
noworker="$(serve "$tmp/noworker")"
nocount="$(serve "$tmp/nocount")"
late="$(serve "$tmp/late")"
noui="$(serve "$tmp/noui")"
dead="http://127.0.0.1:$(free_port)" # nothing listens here

# run <api url> <web url> [timeout s]: prints "<exit code>|<output>"
run() {
  local out code=0
  out="$(API_URL="$1" WEB_URL="$2" SMOKE_TIMEOUT="${3:-1}" "$here/smoke.sh" 2>&1)" || code=$?
  echo "$code|$out"
}

status=0
check() { # $1 = name, $2 = expected exit code, $3 = text the output must contain, $4 = run result
  local code="${4%%|*}" out="${4#*|}"
  if [[ "$code" == "$2" && "$out" == *"$3"* ]]; then
    echo "ok: $1"
  else
    echo "FAIL: $1: expected exit $2 and '$3', got exit $code:"
    echo "$out" | sed 's/^/    /'
    status=1
  fi
}

# Everything answers and is healthy: exit 0, says where the UI is.
check "all up" 0 "UI is up at $good" "$(run "$good" "$good")"
# Health says ok:false: fail and name the service that is down.
check "database down" 1 "postgres" "$(run "$nodb" "$nodb")"
# No ingest worker listening: uploads would wait forever, so fail.
check "no worker" 1 "worker" "$(run "$noworker" "$noworker")"
# Health has no worker count at all: fail rather than pass silently.
check "worker count missing" 1 "worker" "$(run "$nocount" "$nocount")"
# The worker registers a moment after the API is healthy: wait for it, don't fail.
(sleep 1.5 && printf '%s' "$healthy" >"$tmp/late/api/health") &
check "worker joins late" 0 "ingest worker listening" "$(run "$late" "$late" 5)"
# API fine but the UI serves no page: the frontend build is broken.
check "no UI page" 1 "UI" "$(run "$noui" "$noui")"
# API answers directly but not through the UI port: point at the nginx proxy.
check "proxy broken" 1 "nginx" "$(run "$good" "$dead")"
# Nothing answers at all: fail after the timeout and name the API URL.
check "nothing up" 1 "$dead" "$(run "$dead" "$dead")"
exit $status
