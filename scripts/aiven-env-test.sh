#!/usr/bin/env bash
# Test for scripts/aiven-env.sh with a fake `avn` and a fake `secret-tool` keyring.
# Usage: scripts/aiven-env-test.sh   (run by `make check`)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir "$tmp/bin" "$tmp/keyring"
# Fake keyring: `secret-tool lookup service X` prints $tmp/keyring/X if it exists.
cat >"$tmp/bin/secret-tool" <<'FAKE'
#!/usr/bin/env bash
[[ "$1" == lookup && -f "$KEYRING/$3" ]] && cat "$KEYRING/$3"
FAKE
# Fake avn: prints host:port for the two known services, fails like avn for anything else.
cat >"$tmp/bin/avn" <<'FAKE'
#!/usr/bin/env bash
[[ -n "$AIVEN_AUTH_TOKEN" ]] || { echo "not authenticated" >&2; exit 1; }
case "$3" in
  pg-test) echo "pg.example:1111" ;;
  valkey-test) echo "valkey.example:2222" ;;
  *) echo "Service not found" >&2; exit 1 ;;
esac
FAKE
chmod +x "$tmp/bin/secret-tool" "$tmp/bin/avn"

run() { # sources the script in a clean bash; prints "status|DATABASE_URL|VALKEY_URL"
  env -i HOME="$tmp" PATH="$tmp/bin:/usr/bin:/bin" KEYRING="$tmp/keyring" \
    AIVEN_PG_SERVICE=pg-test AIVEN_VALKEY_SERVICE=valkey-test \
    bash -c 'source "$1" >/dev/null 2>&1; echo "$?|${DATABASE_URL:-}|${VALKEY_URL:-}"' _ "$here/aiven-env.sh"
}

status=0
check() { # $1 = name, $2 = expected, $3 = actual
  if [[ "$2" == "$3" ]]; then
    echo "ok: $1"
  else
    echo "FAIL: $1: expected '$2', got '$3'"
    status=1
  fi
}

printf 'token' >"$tmp/keyring/aiven"
printf 'pg-pw\n' >"$tmp/keyring/aiven-pg-app"
printf 'vk/pw@1' >"$tmp/keyring/aiven-valkey"

# URLs use the app user, host:port from avn and passwords from the keyring (trailing newline stripped).
check "builds both URLs" \
  "0|postgresql://app:pg-pw@pg.example:1111/defaultdb?sslmode=require|rediss://default:vk%2Fpw%401@valkey.example:2222" \
  "$(run)"

# A missing keyring entry fails the source, so `source ... && docker compose up` never starts.
rm "$tmp/keyring/aiven-valkey"
check "missing Valkey password fails" "1||" "$(run)"

# avn failing (e.g. no token) also fails the source.
printf 'vk' >"$tmp/keyring/aiven-valkey"
rm "$tmp/keyring/aiven"
check "avn failure fails" "1||" "$(run)"

# Run directly instead of sourced: refuses with a non-zero exit.
check "refuses to run unsourced" "1" "$(bash "$here/aiven-env.sh" >/dev/null 2>&1; echo $?)"

exit $status
