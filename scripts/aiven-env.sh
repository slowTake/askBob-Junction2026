#!/usr/bin/env bash
# Export Aiven connection strings into THIS shell only. Nothing is written to disk.
#
#   source scripts/aiven-env.sh
#
# Needs the avn CLI and your personal Aiven token in the OS keyring (docs/aiven-setup.md).
# Service names are not secret: set them once in your shell profile, e.g.
#   export AIVEN_PG_SERVICE=pg-bobbuilder AIVEN_VALKEY_SERVICE=valkey-bobbuilder

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

_bob_uri() { # $1 = Aiven service name
  AVN_AUTH_TOKEN="$(_bob_secret aiven)" avn service get "$1" --format '{service_uri}'
}

_bob_main() {
  if [[ -z "${AIVEN_PG_SERVICE:-}" || -z "${AIVEN_VALKEY_SERVICE:-}" ]]; then
    echo "Set AIVEN_PG_SERVICE and AIVEN_VALKEY_SERVICE first (see docs/aiven-setup.md)." >&2
    return 1
  fi
  if ! command -v avn >/dev/null 2>&1; then
    echo "avn CLI not found: uv tool install aiven-client" >&2
    return 1
  fi
  local pg valkey
  pg="$(_bob_uri "$AIVEN_PG_SERVICE")" || return 1
  valkey="$(_bob_uri "$AIVEN_VALKEY_SERVICE")" || return 1
  export DATABASE_URL="$pg" VALKEY_URL="$valkey"

  # Optional: an Anthropic key stored the same way (secret-tool store --label=... service anthropic).
  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    local key
    key="$(_bob_secret anthropic)"
    [[ -n "$key" ]] && export ANTHROPIC_API_KEY="$key"
  fi
  echo "Exported DATABASE_URL and VALKEY_URL for $AIVEN_PG_SERVICE / $AIVEN_VALKEY_SERVICE."
}

_bob_main
unset -f _bob_main _bob_uri _bob_secret
