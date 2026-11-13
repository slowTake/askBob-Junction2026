#!/usr/bin/env bash
# RULES.md §5: no hand-written source file over 600 lines.
set -euo pipefail
limit=600
status=0
while IFS= read -r file; do
  lines=$(wc -l <"$file")
  if ((lines > limit)); then
    echo "$file has $lines lines (limit $limit): split it by responsibility"
    status=1
  fi
done < <(git ls-files --cached --others --exclude-standard \
  '*.py' '*.ts' '*.tsx' '*.css' '*.js' '*.sh' | grep -v -e 'package-lock.json' -e '^frontend/dist/')
exit $status
