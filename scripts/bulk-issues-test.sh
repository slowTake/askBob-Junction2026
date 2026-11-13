#!/usr/bin/env bash
# Test for scripts/bulk-issues.sh with a fake `gh` that records the titles it is given.
# Usage: scripts/bulk-issues-test.sh   (run by `make check`)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir "$tmp/bin"
cat >"$tmp/bin/gh" <<'FAKE'
#!/usr/bin/env bash
while (($#)); do
  if [[ "$1" == "--title" ]]; then echo "$2" >>"$GH_LOG"; fi
  shift
done
FAKE
chmod +x "$tmp/bin/gh"

run() { # $1 = file contents (printf format); prints the created titles, comma-separated
  : >"$tmp/log"
  printf "$1" >"$tmp/tasks.tsv"
  PATH="$tmp/bin:$PATH" GH_LOG="$tmp/log" "$here/bulk-issues.sh" "$tmp/tasks.tsv"
  paste -sd, "$tmp/log"
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

# Two tasks, file ends with a newline: both are created.
check "trailing newline" "T1,T2" "$(run 'T1\tarea:backend\td1\nT2\tarea:backend\td2\n')"
# Same two tasks, no newline after the last row: still both.
check "no trailing newline" "T1,T2" "$(run 'T1\tarea:backend\td1\nT2\tarea:backend\td2')"
# Comment lines and blank lines are skipped.
check "comments and blanks" "T1" "$(run '# title\tlabel\tdone when\n\nT1\tarea:backend\td1\n')"
exit $status
