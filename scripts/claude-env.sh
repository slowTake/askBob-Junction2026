#!/usr/bin/env bash
# Source this script: credentials stay in the process environment or OS keyring.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Run: source scripts/claude-env.sh" >&2
  exit 1
fi

_load_claude_key() {
  local key="${ANTHROPIC_API_KEY:-}"
  if [[ -z "${key//[[:space:]]/}" ]] && command -v secret-tool >/dev/null 2>&1; then
    key="$(secret-tool lookup service anthropic 2>/dev/null)" || key=""
  fi
  if [[ -z "${key//[[:space:]]/}" ]] && [[ -t 0 ]]; then
    read -r -s -p "Anthropic API key (hidden): " key
    echo >&2
  fi
  if [[ -z "${key//[[:space:]]/}" ]]; then
    echo "No Anthropic key. Run make up-claude in a terminal, or store it with:" >&2
    echo '  secret-tool store --label="Anthropic API key" service anthropic' >&2
    return 1
  fi
  export ANTHROPIC_API_KEY="$key"
  export LLM_PROVIDER=anthropic
}

_load_claude_key
