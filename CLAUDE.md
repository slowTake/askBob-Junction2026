@AGENTS.md

## Team conventions

- Log every product, data or engineering decision in [docs/decisions.md](docs/decisions.md) in the same PR as the change. Never rewrite an entry; supersede it.
- Never push to `main` directly. Work on short-lived branches, open a PR against `main` (`gh pr create --repo slowTake/bobBuilder --base main`) and rebase-merge once CI is green, so keep each commit small and green on its own.
- Write tests first (red, green, refactor). Expected values come from the spec or a hand calculation, noted next to the assertion, never from running the code.
- `.local/` is git-ignored scratch space for plans and notes that don't belong in the repo.
