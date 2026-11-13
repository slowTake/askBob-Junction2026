#!/usr/bin/env bash
# Creates one issue per line of a tab-separated task file.
# Columns: title <TAB> label <TAB> "done when" text.
# Usage: scripts/bulk-issues.sh docs/tasks.tsv
set -euo pipefail
repo="slowTake/bobBuilder"
file="${1:?usage: $0 <tasks.tsv>}"

while IFS=$'\t' read -r title label done_when; do
  [[ -z "$title" || "$title" == \#* ]] && continue
  gh issue create --repo "$repo" --title "$title" --label "$label" \
    --body "$(printf '## Done when\n\n- [ ] %s' "$done_when")"
done < "$file"
