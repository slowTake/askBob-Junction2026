# Instructions for AI coding agents

You are helping a hackathon team build **bobBuilder**. The engineering rules in `RULES.md` must be followed. The short version:

- **Business logic is pure:** no I/O, no database, no `fetch`, no reading the clock (`Date.now()`, `new Date()`) or randomness inside logic. Pass dates (ISO `YYYY-MM-DD`) and data in as arguments. Every function gets tests next to it, including edge cases.
- **API errors never leak:** one response shape for every endpoint; never return raw error messages or stack traces.
- **Files stay under 600 lines.** Split by responsibility.
- **No secrets** in any committed file: no tokens, passwords or connection strings. Never paste them into chat or tool calls either. Aiven access is described in `docs/aiven-setup.md` and the Verda LLM in `docs/verda-setup.md`; the Aiven MCP server in `.mcp.json` is read-only.
- **Commits** use conventional messages: `type(scope): subject`. Never use `git commit --no-verify` or `git push --no-verify`. If a hook fails, fix the cause.
- Before saying a change is done, run the project's checks (format, lint, type check, tests). Once CI exists, run what CI runs.

## Issues and branches

Work is tracked in GitHub issues on `slowTake/bobBuilder`; see `docs/issues.md`.

- One issue per branch. Before starting, check the issue is assigned to the person you work for (`gh issue view <n>`). Don't pick up unassigned issues on your own.
- Create the branch from the issue: `gh issue develop <n> --checkout`.
- The PR body starts with `Closes #<n>`.
- Work you find that the issue doesn't cover becomes a new issue (`gh issue create`, ask first), not extra scope in the current PR.
