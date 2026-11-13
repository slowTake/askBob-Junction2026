#!/usr/bin/env bash
# Creates or updates the issue labels. Safe to run again.
set -euo pipefail
repo="slowTake/bobBuilder"

label() { gh label create "$1" --repo "$repo" --color "$2" --description "$3" --force; }

label "area:frontend" "1d76db" "UI and demo screens"
label "area:backend"  "0e8a16" "API and server logic"
label "area:data"     "5319e7" "Datasets, embeddings, database"
label "area:infra"    "fbca04" "Deploy, CI, Aiven services"
label "area:pitch"    "d93f0b" "Slides, story, demo video"
label "p0"            "b60205" "Needed for the demo"
label "blocked"       "000000" "Waiting on another issue or person"
