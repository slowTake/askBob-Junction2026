# Issues and the board

How we split and track work. Issues live in `slowTake/bobBuilder`; the board is a GitHub Project owned by slowTake.

## Flow

1. **Claim** an issue by assigning yourself (`gh issue edit <n> --add-assignee @me`) and moving its card to **In Progress**.
2. **At most two** issues in progress per person.
3. **Branch** from the issue: `gh issue develop <n> --checkout`.
4. **PR** body starts with `Closes #<n>`. Merging the PR closes the issue and moves the card to **Done**.
5. **New work** you find becomes a new issue, not extra scope in your PR.
6. Every few hours: a five-minute sync in front of the board.

Aim for 10–20 chunky issues, a few hours each, each with a "Done when" list. Use the **Task** or **Bug** form and add one `area:` label.

## One-time setup

**Everyone:** `gh auth login`. To move cards from the CLI as well, `gh auth refresh -h github.com -s project`.

**Labels** (anyone with write access, once): `scripts/labels.sh`.

**Board** (slowTake, once, in the GitHub UI):

1. Profile → **Projects → New project → Board**, named `bobBuilder`.
2. Edit the **Status** field to: Todo, In Progress, In Review, Done.
3. Project **⋯ → Workflows**, turn on:
   - *Auto-add to project*: repository `bobBuilder`, filter `is:issue,pr is:open`.
   - *Item added to project* → Todo.
   - *Item closed* and *Pull request merged* → Done.
   - *Item reopened* → In Progress.
4. Project **⋯ → Settings → Manage access**: add the rest of the team with **Write**.
5. Link it from the repo: **bobBuilder → Projects → Link a project**.

Moving a card to In Progress or In Review is manual; no built-in workflow fires on assignment.

## Bulk-creating the first issues

After the first-hour planning, write the tasks into a tab-separated file (see `docs/tasks.example.tsv`) and run:

```bash
scripts/bulk-issues.sh docs/tasks.tsv
```

Auto-add puts them on the board.
