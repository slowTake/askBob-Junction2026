# Engineering rules

Our rules for askBob, adapted from the ones we used on Lease Loop. `make check` runs the format, lint, type, test, build and file-size checks; CI ([ci.yml](.github/workflows/ci.yml)) enforces them.

## 1. Conventional commits

Every commit message has the form `type(scope): what changed`, for example:

```text
feat(builder): add step list
fix(api): return 404 for a missing project
docs(aiven): add the connection steps
```

Types: `feat`, `fix`, `test`, `refactor`, `docs`, `style`, `chore`, `ci`, `perf`. Small, frequent commits tell the story of the build.

## 2. Hooks stay on

The repository ships no Git hooks; CI is what enforces the checks. If you have hooks of your own, such as a secret scan, **never use `--no-verify`**. If a hook fails, fix the cause.

## 3. Business logic is pure and tested

- Keep logic in plain functions with no database, no network calls and no clock or randomness. Pass dates and data in as arguments.
- Every logic function has tests next to it, including edge cases.
- Test the logic, not the markup.

## 4. Errors never leak

API responses never contain raw error messages or stack traces. Log the detail on the server and return a generic error to the client. Use one response shape for every endpoint.

## 5. Small files

No hand-written source file over **600 lines**. Split by responsibility before you get there.

## 6. No secrets in Git

Nothing secret belongs in the repo: no API keys, passwords, tokens or connection strings. That includes `.env` files, config, notebooks and screenshots. `.env` is git-ignored; put examples in `.env.example`. Aiven credentials are fetched per person, see [docs/aiven-setup.md](docs/aiven-setup.md#secrets-team-rules).

## 7. Decisions are written down

Every product, data or engineering decision goes in [docs/decisions.md](docs/decisions.md) in the same PR as the change. An entry is never rewritten, only superseded by a new one.

## 8. CI is green

CI runs on every pull request and every push to `main`: format, lint, type check, file size, tests, build and container checks, plus commit messages on pull requests. Run `make check` locally before saying a change is done. A green check on the last commit before the deadline matters.
