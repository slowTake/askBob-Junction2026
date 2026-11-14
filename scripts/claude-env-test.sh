#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"
cat >"$tmp/bin/secret-tool" <<'FAKE'
#!/usr/bin/env bash
[[ "$1 $2 $3" == 'lookup service anthropic' && -n "${FAKE_KEY:-}" ]] || exit 1
printf '%s' "$FAKE_KEY"
FAKE
chmod +x "$tmp/bin/secret-tool"

run() {
  env -i PATH="$tmp/bin:/usr/bin:/bin" ANTHROPIC_API_KEY="$1" FAKE_KEY="$2" \
    bash -c 'source "$1" >/dev/null 2>&1 || exit 1; [[ "$ANTHROPIC_API_KEY" == "$2" && "$LLM_PROVIDER" == anthropic ]]' \
    _ "$here/claude-env.sh" "$3" </dev/null
}

run 'environment-placeholder' 'keyring-placeholder' 'environment-placeholder'
echo 'ok: existing environment key takes precedence'
run '' 'keyring-placeholder' 'keyring-placeholder'
echo 'ok: keyring supplies a missing key'
run '   ' 'keyring-placeholder' 'keyring-placeholder'
echo 'ok: whitespace environment key falls back to keyring'
if run '' '' ''; then echo 'FAIL: missing key must fail' >&2; exit 1; fi
if run '' '   ' ''; then echo 'FAIL: blank key must fail' >&2; exit 1; fi
echo 'ok: missing or blank key fails without prompting in automation'
if bash "$here/claude-env.sh" >/dev/null 2>&1; then
  echo 'FAIL: must be sourced' >&2; exit 1
fi
echo 'ok: refuses to run unsourced'
