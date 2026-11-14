#!/usr/bin/env bash
# Starts the API, the ingest worker and nginx in one container (D-034). If any of them
# exits, the others are stopped and the container exits, so Runtime restarts it whole.
set -uo pipefail
api="" worker="" web=""
grace="${STOP_GRACE_S:-20}"

# Ask each process to stop (nginx gracefully, with QUIT), give them STOP_GRACE_S seconds,
# then kill what is left: a worker in the middle of a long job would otherwise hold the
# container until the platform kills it. A cut-off job is requeued by the next worker.
stop() {
  kill -TERM $api $worker 2>/dev/null
  kill -QUIT $web 2>/dev/null
  for _ in $(seq "$grace"); do
    kill -0 $api $worker $web 2>/dev/null || break
    sleep 1
  done
  kill -KILL $api $worker $web 2>/dev/null
  wait
}
trap 'stop; exit 0' TERM INT

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api=$!

# The API creates the schema on start-up; start the worker (which checks it too) after.
for _ in $(seq 120); do
  kill -0 "$api" 2>/dev/null || break
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" \
    2>/dev/null && break
  sleep 1
done

python -m app.worker &
worker=$!
nginx -e /dev/stderr -g 'daemon off;' &
web=$!

wait -n
echo "start.sh: a process exited; stopping the container" >&2
stop
exit 1
