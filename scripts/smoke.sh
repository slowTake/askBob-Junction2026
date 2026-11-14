#!/usr/bin/env bash
# Checks that a started stack is built and reachable: the API answers and is healthy,
# an ingest worker listens, nginx proxies /api, and the UI page is served.
# Retries until SMOKE_TIMEOUT seconds have passed, since containers may still be starting.
# Usage: scripts/smoke.sh   (run by `make smoke` and after `make up*`)
#   API_URL (default http://localhost:8000), WEB_URL (default http://localhost:8080)
set -euo pipefail
api="${API_URL:-http://localhost:8000}"
web="${WEB_URL:-http://localhost:8080}"
deadline=$((SECONDS + ${SMOKE_TIMEOUT:-60}))

fail() {
  echo "smoke: FAIL: $*" >&2
  exit 1
}

# fetch <url> <regex>: retries until the response body matches <regex> (bash =~); prints
# the last body. Returns 1 at the deadline. Only 2xx bodies count (curl -f).
fetch() {
  local body=""
  while :; do
    body="$(curl -sf --max-time 5 "$1" 2>/dev/null)" || body=""
    if [[ "$body" =~ $2 ]]; then
      echo "$body"
      return 0
    fi
    ((SECONDS < deadline)) || {
      echo "$body"
      return 1
    }
    sleep 1
  done
}

health="$(fetch "$api/api/health" '"ok":true')" || {
  [[ -n "$health" ]] || fail "the API does not answer at $api/api/health. Is the backend container up? Try: docker compose ps; make logs"
  fail "the API answers but is not healthy: $health (postgres or valkey is unreachable; check DATABASE_URL/VALKEY_URL)"
}
echo "smoke: ok: API healthy at $api"

# The worker registers with the queue a moment after it starts, so wait for it too.
fetch "$api/api/health" '"ingest_workers":[1-9]' >/dev/null ||
  fail "no ingest worker is listening, so uploads would wait forever. Check: docker compose logs worker"
echo "smoke: ok: ingest worker listening"

fetch "$web/api/health" '"ok":true' >/dev/null ||
  fail "the API answers at $api but not through nginx at $web/api. Is the frontend container up, and does BACKEND_URL point at the API? Check: docker compose logs frontend"
echo "smoke: ok: nginx proxies /api"

fetch "$web/" '<title>AskBob</title>' >/dev/null ||
  fail "the UI page is not served at $web/. The frontend build may be broken: docker compose logs frontend"
echo "smoke: ok: UI is up at $web"
