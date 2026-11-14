#!/usr/bin/env bash
# Starts the API, the ingest worker and nginx in one container (D-034). If any of them
# exits, the others are stopped and the container exits, so Runtime restarts it whole.
set -uo pipefail
pids=()
stop() {
  kill "${pids[@]}" 2>/dev/null
  wait
}
trap 'stop; exit 0' TERM INT

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api=$!
pids+=("$api")

# The API creates the schema on start-up; start the worker (which checks it too) after.
for _ in $(seq 120); do
  kill -0 "$api" 2>/dev/null || break
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" \
    2>/dev/null && break
  sleep 1
done

python -m app.worker &
pids+=($!)
nginx -e /dev/stderr -g 'daemon off;' &
pids+=($!)

wait -n
echo "start.sh: a process exited; stopping the container" >&2
stop
exit 1
