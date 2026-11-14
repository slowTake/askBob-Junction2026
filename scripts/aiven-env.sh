#!/usr/bin/env bash
# Export Aiven connection strings into THIS shell only. Nothing is written to disk.
#
#   source scripts/aiven-env.sh      # or just: make up-aiven
#
# Host and port come from the Aiven API with your personal token. Passwords come from your
# OS keyring, because the API masks them for our tokens: the password inside `service_uri`
# is a placeholder that can't log in. See docs/aiven-setup.md step 5 for the keyring entries.
#
# Project and service names are not secret. The defaults below are the team's services;
# override any of them in your shell profile.

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Run this with 'source scripts/aiven-env.sh', otherwise the variables vanish." >&2
  exit 1
fi

_bob_secret() { # $1 = keyring service name
  if command -v secret-tool >/dev/null 2>&1; then
    secret-tool lookup service "$1"
  elif command -v security >/dev/null 2>&1; then
    security find-generic-password -s "$1" -w 2>/dev/null
  fi
}

_bob_hostport() { # $1 = Aiven service name; prints host:port
  AIVEN_AUTH_TOKEN="$(_bob_secret aiven)" avn service get "$1" \
    --format '{service_uri_params[host]}:{service_uri_params[port]}'
}

_bob_urlencode() { # $1 = string; percent-encodes everything but unreserved characters
  local s="$1" out="" c i
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [A-Za-z0-9._~-]) out+="$c" ;;
      *) out+="$(printf '%%%02X' "'$c")" ;;
    esac
  done
  printf '%s' "$out"
}

_bob_password() { # $1 = keyring service name, $2 = what it is (for the error message)
  local pw
  pw="$(_bob_secret "$1" | tr -d '\r\n')"
  if [[ -z "$pw" ]]; then
    echo "No $2 password in the keyring. Copy it from the Aiven console (service → Users) and run:" >&2
    echo "  secret-tool store --label=\"$2\" service $1" >&2
    return 1
  fi
  _bob_urlencode "$pw"
}

_bob_main() {
  : "${AIVEN_PROJECT:=junction-stoa-winners}" "${AIVEN_PG_SERVICE:=pg-2c3baae}"
  : "${AIVEN_VALKEY_SERVICE:=valkey-bobbuilder}" "${AIVEN_PG_USER:=app}"
  export AIVEN_PROJECT
  if ! command -v avn >/dev/null 2>&1; then
    echo "avn CLI not found: uv tool install aiven-client" >&2
    return 1
  fi
  local pg_at valkey_at pg_pw valkey_pw
  pg_pw="$(_bob_password "aiven-pg-$AIVEN_PG_USER" "Aiven PostgreSQL $AIVEN_PG_USER")" || return 1
  valkey_pw="$(_bob_password aiven-valkey "Aiven Valkey default")" || return 1
  pg_at="$(_bob_hostport "$AIVEN_PG_SERVICE")" || return 1
  valkey_at="$(_bob_hostport "$AIVEN_VALKEY_SERVICE")" || return 1
  export DATABASE_URL="postgresql://$AIVEN_PG_USER:$pg_pw@$pg_at/defaultdb?sslmode=require"
  export VALKEY_URL="rediss://default:$valkey_pw@$valkey_at"

  # Optional: an Anthropic key stored the same way (secret-tool store --label=... service anthropic).
  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    local key
    key="$(_bob_secret anthropic)"
    [[ -n "$key" ]] && export ANTHROPIC_API_KEY="$key"
  fi
  echo "Exported DATABASE_URL ($AIVEN_PG_USER@$AIVEN_PG_SERVICE) and VALKEY_URL ($AIVEN_VALKEY_SERVICE)."
}

_bob_main
_bob_status=$?
unset -f _bob_main _bob_hostport _bob_urlencode _bob_password _bob_secret
return $_bob_status
