# Aiven setup

How to get access to our Aiven services and connect to them. We use Aiven for our managed data services (and for the "Best Use of Aiven" prize), so everyone should be able to reach them in a few minutes.

## Current services

| Service | Name in console | Plan | Status |
|---|---|---|---|
| PostgreSQL | `<pg-service>` _(TODO: fill in)_ | _TODO_ | Running |
| Valkey | `<valkey-service>` _(TODO: create on the free plan, then fill in)_ | Free | Not created yet |

Ask before creating new services: see [Credits and cost](#credits-and-cost). What each service is for is recorded in [decisions.md](decisions.md) (D-005).

| Service | What the app uses it for |
|---|---|
| PostgreSQL | The building model (documents, pages, elements), the Q&A log, `pg_trgm` for fuzzy label search, `pgvector` for embeddings |
| Valkey | The ingest job queue (RQ), live progress events (pub/sub), the answer cache |

The app creates its tables and the `vector` and `pg_trgm` extensions on first start.

## 1. Accept the invite

You've been invited to our Aiven organization by email and given the **organization admin** role.

1. Open the invite email from Aiven and follow the link. If you don't have an Aiven account yet, the link signs you up.
2. Log in at <https://console.aiven.io> and check you can see our project and the PostgreSQL service.

## 2. Create your own API token (for the CLI)

Tokens are **personal**: never share yours or use someone else's. A token acts as you, with your full permissions.

1. In the console: **User profile → Tokens → Generate token**.
2. Store it in your OS keyring, not in a file or shell profile:
   - **Linux:** `secret-tool store --label="Aiven API token" service aiven` (paste the token when prompted)

## 3. Install the CLI

```bash
uv tool install aiven-client     # or: pipx install aiven-client
```

Pass the token to a single command instead of exporting it or running `avn user login` (which saves the token to a plaintext file):

```bash
# Linux
AVN_AUTH_TOKEN=$(secret-tool lookup service aiven) avn project list
# macOS
AVN_AUTH_TOKEN=$(security find-generic-password -s aiven -w) avn project list
```

An alias saves typing, e.g. `alias avnk='AVN_AUTH_TOKEN=$(secret-tool lookup service aiven) avn'`.

## 4. Connect to PostgreSQL

Fetch the connection string when you need it rather than copying it anywhere:

```bash
psql "$(avnk service get <pg-service> --format '{service_uri}')"
```

Or copy the **Service URI** from the service's **Overview** page in the console. You need a `psql` client (`sudo apt install postgresql-client`, `brew install libpq`).

If we use vector search, the extension is enabled once per database with `CREATE EXTENSION vector;`. Check whether someone already did with `\dx`.

## 5. Run the app against Aiven

`scripts/aiven-env.sh` fetches the PostgreSQL and Valkey service URIs with your own token and exports them as `DATABASE_URL` and `VALKEY_URL` for the current shell only. Nothing is written to disk.

```bash
export AIVEN_PG_SERVICE=<pg-service> AIVEN_VALKEY_SERVICE=<valkey-service>   # names, not secrets
source scripts/aiven-env.sh
make up            # docker compose up --build, against Aiven
```

If you also keep an Anthropic API key in the keyring (`secret-tool store --label="Anthropic API key" service anthropic`), the script exports it as `ANTHROPIC_API_KEY` too.

No network or no Aiven access? `make up-local` runs the same app against local Postgres and Valkey containers.

## Secrets: team rules

- **Never commit** a connection string, password or token. That includes `.env` files, config files, notebooks and screenshots.
- **Don't paste secrets into chat** (Discord, Slack, WhatsApp) or into AI tools. Everyone can fetch credentials themselves (steps 2–4), so there should be no need to.
- The app reads its connection string at runtime from the environment of the process that runs it (set by the host's secret settings or inline when running locally), and never from a file in the repo.
- The deployed app gets its **own database user** (`avn service user-create --username app <pg-service>`), so we can rotate it without breaking anyone's local setup.

## Credits and cost

- Everything in the project bills to the same organization and the **$50 sign-up credit**. Free plans (PostgreSQL, Valkey, Kafka, OpenSearch) cost nothing; anything else (e.g. ClickHouse) spends credits.
- Since we're all admins, **say in the team chat before creating or upgrading a service**, and **power off paid services** when not in use (`avnk service update <service> --power-off`).

## Log what you do

Aiven asked us to document how we use their services. When you create a service, change a schema, or measure something (latency, cost, speed-ups), tell the person keeping the usage log, with what you did, why, and what it enabled.

## After the hackathon

Reset service passwords (service **Users** tab → **Reset password**), revoke your API token, and power off or delete services we no longer need.
