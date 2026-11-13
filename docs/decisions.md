# Decision log

Product, data and engineering decisions, numbered `D-NNN`. Add the next number, an index row and an entry in the same PR as the change. Never rewrite an entry; supersede it with a new one and mark the old one as superseded.

| ID    | Date       | Decision                                            | Status   |
| ----- | ---------- | --------------------------------------------------- | -------- |
| D-001 | 2026-11-14 | Adopt the Lease Loop engineering rules, stack-neutral | Accepted |
| D-002 | 2026-11-14 | Track work in GitHub issues with one board            | Accepted |
| D-009 | 2026-11-14 | Kimi K3.1 Pro on Verda as a secondary LLM; keys in keyrings | Accepted |

## D-001: Adopt the Lease Loop engineering rules, stack-neutral

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** We want the same working discipline we had on Lease Loop from day one, but have not chosen the stack yet.

**Decision:** Carry over the generic rules (conventional commits, hooks stay on, pure tested logic, no leaked errors, small files, no secrets, decision log, green CI). Drop the Lease Loop challenge rules (no AI in the product, integer-cent money, four UI languages, audit trail). Hooks and CI are added once the stack is chosen.

**Consequences:** `RULES.md` is not yet enforced by tooling; until then each of us checks it by hand.

## D-002: Track work in GitHub issues with one board

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Four people and their agents work in parallel for about 36 hours, so everyone needs to see who owns what and what is left.

**Decision:** Every chunk of work is a GitHub issue with a "Done when" list, created from a form or in bulk from a task file. People claim issues by assigning themselves (at most two in progress each), branch with `gh issue develop`, and close them with `Closes #n` in the PR. One GitHub Project board owned by slowTake, linked to the repo, shows status. Assignment and status moves are not automated. Details in `docs/issues.md`.

**Consequences:** Blank issues are disabled, so every issue needs a form. The board's built-in workflows are set up by hand in the UI and are not versioned in the repo.

## D-009: Kimi K3.1 Pro on Verda as a secondary LLM; keys in keyrings

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** The Q&A agent runs on Claude Opus 5.5 through the Anthropic SDK (D-006). Every team also gets Verda credits, and Verda's inference API serves Kimi K3.1 Pro. Verda speaks only the OpenAI Chat Completions and Responses APIs: `POST /v1/messages` returns 404, so the Anthropic client can't be pointed at it. A test call to Kimi K3.1 Pro worked (HTTP 200, about 1.2 s).

**Decision:** Claude stays the Q&A agent. Kimi K3.1 Pro on Verda (`kimi-k3-1-pro`, `https://inference.verda.com/v1`, via an OpenAI SDK) is available for side tasks where the Anthropic-only features of D-006 aren't needed, such as cheap bulk calls or experiments, and for the Verda prize. Each person creates their own Verda key in our project and keeps it in their OS keyring, passing it to one process at a time. The deployed app reads any key from the host's secret settings. No key goes in the repo, a `.env` file or chat. Setup in `docs/verda-setup.md`.

**Consequences:** Code that uses Verda has its own OpenAI-compatible client, separate from the Anthropic one; moving the Q&A agent itself to Verda would mean a rewrite and a new decision superseding D-006. Verda lists no embedding model, so embeddings need a separate decision.
