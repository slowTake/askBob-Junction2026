# Verda setup

How to get access to Kimi K3.1 Pro on Verda and call it. The Q&A agent runs on Claude by default and on Kimi with `LLM_PROVIDER=verda` (see [D-006, D-009 and D-014](decisions.md)). Verda's inference API is OpenAI-compatible, so any OpenAI SDK works with a different base URL and key. It does not speak the Anthropic Messages API.

## What we use

| | |
|---|---|
| Model | Kimi K3.1 Pro, model ID `kimi-k3-1-pro` |
| Base URL | `https://inference.verda.com/v1` |
| Keyring service name | `verda` |

Prices and rate limits per model are in the Console under **Inference → Models**. Inference pauses when the project balance runs low.

## 1. Join the project

1. Accept the invite to our Verda project and log in at <https://console.verda.com>.
2. If you have a credit coupon, redeem it **inside our project** (credits go to the project you redeem from): **Project Dashboard → Billing & settings → Top-up → Credit coupon → Apply coupon**. Each coupon works once per account.

## 2. Create your own API key

Keys are **personal**: create your own instead of borrowing someone else's, so one can be revoked without breaking the others.

1. In the Console: **Inference → Models → Kimi K3.1 Pro → Create API key**, or the **Credentials** page.
2. The key is shown **only once**. Store it straight in your OS keyring, not in a file or shell profile:
   - **Linux:** `secret-tool store --label="Verda inference key" service verda` (paste the key when prompted)
   - **macOS:** `security add-generic-password -s verda -a "$USER" -w` (paste the key when prompted)

Verda's own quickstart puts the key in a `.env` file. We don't; see [Secrets: team rules](aiven-setup.md#secrets-team-rules).

## 3. Test it

Pass the key to a single command instead of exporting it:

```bash
# Linux; on macOS use $(security find-generic-password -s verda -w)
curl -s https://inference.verda.com/v1/chat/completions \
  -H "Authorization: Bearer $(secret-tool lookup service verda)" \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi-k3-1-pro","messages":[{"role":"user","content":"Reply with exactly: pong"}],"max_tokens":2000}'
```

A working key returns HTTP 200 with `"content": "pong"`.

## 4. Run the Q&A agent on Kimi

The app reads the key from `VERDA_API_KEY` and picks Kimi with `LLM_PROVIDER=verda`. Set both for one command only:

```bash
LLM_PROVIDER=verda VERDA_API_KEY=$(secret-tool lookup service verda) make up-local
```

Without a key the agent answers with "The language model is not configured on the server." `VERDA_MODEL` overrides the model ID.

## 5. Call it from other code

The OpenAI SDKs read `OPENAI_BASE_URL` and `OPENAI_API_KEY` from the environment, so set them for one process only:

```bash
OPENAI_BASE_URL=https://inference.verda.com/v1 \
OPENAI_API_KEY=$(secret-tool lookup service verda) \
  <command that starts the app>
```

The deployed app gets the key from the host's secret settings (for example the **Secrets** tab of an Aiven Runtime app), never from the repo.

## Things to know

- **Kimi reasons before it answers.** The reasoning is returned separately (`reasoning_content`) and counts toward `max_tokens`. With a small `max_tokens`, `content` can come back empty, so set it to a few thousand.
- **With tools, use a final-answer tool instead of `response_format`.** When a request has both tools and a JSON-schema `response_format`, Kimi skips the tools and answers right away, inventing citations. The agent therefore asks for its final answer as a `final_answer` tool call and sets `tool_choice: "required"` (#51).
- **Images go in a user message.** Tool messages are text-only; Kimi reads an `image_url` data URL in a user message placed after the tool messages.
- **Prompt caching is automatic.** Repeated prefixes are billed at the cheaper cached-input price, so keep a fixed system prompt at the start of each request.
- **No embedding model** is listed on Verda's managed inference. Embeddings need another API, a local model, or our own container on Verda.
- **Failed or interrupted requests** aren't charged.

## After the hackathon

Delete your API key on the **Credentials** page and remove it from your keyring (`secret-tool clear service verda`).
