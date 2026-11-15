# bobBuilder

Ask construction drawings questions in plain language and get answers you can check: every answer cites the exact spot on the drawing (or the exact IFC element) it came from. Built for Stoa's "Make Blueprints Talk" challenge at Junction. The brief is in [docs/challenge.md](docs/challenge.md).

## How it works

```
 upload (IFC / PDF / PNG)                                 question
          │                                                  │
          ▼                                                  ▼
 ┌──────────────┐  job   ┌────────────────────────────┐   ┌──────────────────────────┐
 │ API          │──────▶ │ worker (RQ)                │   │ agent (Claude Opus 5.5)  │
 │ FastAPI      │ Valkey │  reader per format         │   │  tools: find_elements,   │
 └──────────────┘        │  ├ ifc: ifcopenshell       │   │  get_element,            │
        ▲                │  ├ pdf: PyMuPDF text layer │   │  view_region (image),    │
        │ SSE progress   │  └ image: Tesseract + CV   │   │  measure_distance        │
        │ (Valkey pub/sub)│  → elements + provenance   │   └────────────┬─────────────┘
        │                │  → IFC export + 3D mesh    │                │ cited JSON answer
        │                └─────────────┬──────────────┘                ▼
        │                              ▼                     server checks every citation
        │                ┌────────────────────────────┐      against what the tools returned
        └────────────────│ PostgreSQL (Aiven)         │◀─────────────────┘
                         │ documents · pages ·        │
                         │ elements · qa_log          │
                         └────────────────────────────┘
```

1. **Readers** (IFC, DXF, PDF, image; exact CAD/vector geometry first, pixels last) turn each file into **elements** (rooms, walls, doors, dimensions, scale notes, IFC products). Each element keeps its **provenance**: a bounding box on the rendered page or an IFC GlobalId, plus `source` and `confidence`.
2. When a drawing's scale is known, the worker also writes an **IFC model** (with a `Bob_Provenance` property set on each product) and a **3D mesh** for the viewer. IFC uploads are meshed directly.
3. The **agent** answers only through read-only tools over those elements. It can look at regions of the drawing as images to check OCR or computer-vision results. Its answer is structured JSON with citations, and the server marks it **verified** only if every citation points at evidence a tool returned.
4. The **UI** shows the answer. Clicking a citation spotlights the region on the drawing or highlights the element in 3D.

Why it's built this way: [docs/decisions.md](docs/decisions.md).

### Supported formats

Every format goes through the same pipeline and ends up as an IFC model plus the same elements ([docs/model.md](docs/model.md)).

| Upload | How it is read | 3D model |
|---|---|---|
| IFC (IFC2X3, IFC4) | indexed directly, exact | its own geometry |
| DXF | named layers (walls, doors, rooms…); vision on the rendered page when layer names mean nothing | from footprints |
| DWG | converted to DXF (needs LibreDWG `dwg2dxf` or ODA File Converter on the server) | from footprints |
| PDF, SVG | text, vector walls and printed labels; doors, windows and fixtures from the floor-plan model; OCR and the model for scanned pages | when the scale is printed |
| PNG, JPEG, TIFF (multi-page), WebP, BMP, GIF | OCR + the floor-plan model (rooms, walls, doors, windows, fixtures), pixel heuristics when the model is off | when DPI and scale are known |

### Aiven, Verda and the Claude API

**Aiven** runs our data services ([D-005](docs/decisions.md), setup in [docs/aiven-setup.md](docs/aiven-setup.md)):
- **Aiven for PostgreSQL** holds the building model (documents, pages, elements with provenance) and `qa_log`: every question and answer with whether it verified, the model, latency and tokens. `pg_trgm` powers fuzzy label search; `pgvector` is enabled for embeddings.
- **Aiven for Valkey** is the ingest job queue (RQ), the pub/sub channel for live progress that the browser gets over SSE, and the answer cache, keyed by question and document version.
- **Aiven Runtime** hosts the demo: one app, `askBob`, runs the UI's nginx, the API and the ingest worker in one container built from the root `Dockerfile` ([D-034](docs/decisions.md)). See [Deploy on Aiven Runtime](#deploy-on-aiven-runtime).
- Connection details come from `avn` and your OS keyring at start-up (`make up-aiven`) and are never written to a file. `make up-local` runs the same app against local containers when offline.

**The Claude API** does the reasoning:
- **The Q&A agent** (`claude-opus-5-5`, effort `high`) answers only through read-only tools over the extracted elements, can look at regions of a drawing as images, and returns structured JSON with citations that the server checks before marking an answer verified ([D-006](docs/decisions.md), [D-031](docs/decisions.md)).
- **Upscale** (`claude-haiku-5-5`) fills gaps in a page's elements in one vision pass ([D-027](docs/decisions.md)).
- **Sketch redraw** (`claude-opus-5-5`) redraws photographed hand sketches as clean plans in a draw, compare, correct loop, with no invented measurements ([D-028](docs/decisions.md), [D-029](docs/decisions.md)).

**Verda** is the second model provider. With `LLM_PROVIDER=verda`, the same agent runs on **Kimi K3.1 Pro** through Verda's OpenAI-compatible endpoint: same prompt, tools, citation check, cache and `qa_log`, so the two can be compared on the eval set ([D-009](docs/decisions.md), [D-020](docs/decisions.md), setup in [docs/verda-setup.md](docs/verda-setup.md)). Upscale uses it too; the sketch redraw needs Claude and says so.

## Run it

**With Aiven** (shared setup; first follow [docs/aiven-setup.md](docs/aiven-setup.md)):

```bash
make up-aiven      # UI on http://localhost:8080, API on :8000
                   # URLs from avn + your keyring (aiven-pg-app, aiven-valkey); see aiven-setup.md step 5
```

**Offline**, with local Postgres and Valkey containers: `make up-local`.

**With Claude locally:** run `make up-claude`. It uses `ANTHROPIC_API_KEY` from
your environment, then the Linux keyring entry `service anthropic`, or asks for
the key with hidden input. To save it in the keyring first, run
`secret-tool store --label="Anthropic API key" service anthropic` and paste it at
the prompt. The key is never written to the repository. For Aiven, run
`source scripts/claude-env.sh && make up-aiven`.
Changing a key requires recreating the backend (`docker compose restart` keeps
the old environment); the `make up-*` commands apply environment changes.

Every `make up-*` builds the images, starts the stack in the background and
then runs `make smoke`, which waits up to 3 minutes and fails, saying what to look at,
unless the API is healthy, an ingest worker listens, nginx proxies `/api` and the
UI page is served on :8080. Follow the logs with `make logs`; run `make smoke`
again at any time to check a running stack.

The UI container's nginx sends `/api` to `BACKEND_URL` (default
`http://backend:8000`, the Compose service), so the same image can run on its own,
for example on Aiven Runtime, pointed at a backend elsewhere. Without a reachable
backend it still serves the UI and answers `/api` with 502. `BACKEND_URL` is
`http(s)://host[:port]` with no path, and outside Compose the host must be a full
name (`api.example.com`); the container refuses to start otherwise and says why.

Raster ingest reports OCR, geometry and annotation progress. The optional vision
model has a 90-second wait budget per page, then ingest continues with pixel
heuristics. Set `VISION_TIMEOUT_S` when starting Docker to allow a longer wait.

**Exact room boundaries with a matching DXF:** upload `floor.png` and `floor.dxf`
(the filename before the extension must match). Either upload order works. The PNG
keeps its original appearance, while the native DXF supplies every room's identity,
polygon and area, including open-plan kitchens and rooms OCR missed. Registration
uses the shared printed room numbers and rejects poor or ambiguous matches. The
document shows **Ready · CAD rooms** when this succeeds. Uploads without a valid
companion keep their raster reading; uncertain room boundaries are label-only.

**On Kimi instead of Claude** (D-020; needs your own Verda key, see [docs/verda-setup.md](docs/verda-setup.md)): pass the provider and key to the one command that starts the app.

```bash
LLM_PROVIDER=verda VERDA_API_KEY=$(secret-tool lookup service verda) make up-local
```

**Without Docker** (fastest edit loop; needs `uv`, Node 22 and `tesseract` installed):

```bash
export DATA_DIR=$PWD/.local/data   # plus DATABASE_URL, VALKEY_URL, ANTHROPIC_API_KEY
make dev-api      # terminal 1: API with reload on :8000
make dev-worker   # terminal 2: ingest worker
make dev-web      # terminal 3: UI on :5173, proxies /api to :8000
```

Docker needs the daemon running and your user in the `docker` group (`sudo systemctl start docker`, `sudo usermod -aG docker $USER`, then log in again).

### Deploy on Aiven Runtime

The whole app runs as one Runtime app (D-034): nginx on port 8080 serves the UI and
proxies `/api` to the API in the same container, and the ingest worker runs beside it.
In the Aiven Console, project `junction-stoa-winners` → **Runtime** → the app → configure:

| Setting | Value |
|---|---|
| Repository, branch | `slowTake/bobBuilder`, `main` |
| Manifest | `Dockerfile` (the root one; not `docker-compose.yml`, which would create extra Postgres and Valkey services) |
| Build context directory | `/` (the repo root) |
| Containerfile path | `/Dockerfile` |
| Port | `8080`, HTTP |
| Cloud, plan | `aws-eu-central-1`, at least `startup-50-2560` (OCR needs the memory) |

Secrets, in the app's settings (type them in the console, never in chat or a file):
- `DATABASE_URL` and `VALKEY_URL`: connect `pg-2c3baae` and `valkey-bobbuilder` under
  **Connected services** with those variable names, or paste their service URIs as secrets.
- `ANTHROPIC_API_KEY`; optionally `LLM_PROVIDER=verda` with `VERDA_API_KEY`.
- `APP_PASSWORD`: the shared password on the login page. Without it the API is open to anyone with the URL ([D-048](docs/decisions.md)).

Pushing does not redeploy: after a merge, use **Actions → Deploy latest commit**. Limits
of this setup: files live on the container's own disk, so a redeploy or restart loses
uploads, page images and models while Postgres still lists the documents (re-upload
after a redeploy); there is no vision service, so raster ingest uses pixel heuristics.
Check the image locally with `make runtime-image-check`.

## Layout

```
backend/app/
  domain/      pure logic, tests next to it: vocabulary (MH, OH, door tags), dimensions
               and scales, geometry, token classification, citation checking
  ingest/      readers (ifc, pdf, image), OCR, room/wall vision, persist, the worker job
  bim/         IFC writer (ifcopenshell.api) and IFC -> mesh for three.js
  qa/          agent loop, tools, prompt, /api/ask service (cache + log)
  api/         HTTP routes: documents, events (SSE), ask, health
  envelope.py  the one response shape: {ok, data, error}
vision/        floor-plan model service (CubiCasa5k, CPU PyTorch, D-022): page image in, polygons out
backend/eval/  eval set from the dataset, and a runner: accuracy per source and type, verified rate
frontend/src/
  api/         typed client, SSE parser, types mirroring backend/app/schemas.py
  components/  drawing viewer (spotlight overlay), 3D viewer, ask panel, document list
  styles/      tokens.css mirrors DESIGN.md
```

## Where to work next

| To improve | Start in |
| --- | --- |
| Vocabulary (new room or fixture codes, Swedish/English drawings) | `backend/app/domain/vocab.py` |
| Doors, windows and apartments from vector PDFs | `backend/app/ingest/pdf_vector.py` (walls done) |
| Fixture types (WC, washbasin, bathtub, shower) from DXF symbols | `backend/app/ingest/dxf_reader.py` |
| Scale for raster plans (fit dimension strings to dimension lines) | `backend/app/ingest/annotate.py` (TODO) |
| Rooms whose door openings leak the flood fill | `backend/app/ingest/rooms.py` (TODO) |
| A new file format (DXF, DWG via converter) | write a reader, register it in `backend/app/ingest/registry.py` |
| A new agent capability | add a tool in `backend/app/qa/tools.py` and record its evidence |
| Measuring accuracy | against `make up-local`, in `backend/`: `uv run python -m eval.build_eval_set <dataset-dir> --out ../.local/eval.jsonl`, then `uv run python -m eval.run_eval ../.local/eval.jsonl` (scoring rules: D-019) |

**Current limits:** for raster images, rooms, walls, doors, windows and fixtures come from the floor-plan model (`vision`, D-022): usually right but not exact, and a large sheet takes minutes on CPU. Without the `vision` service, walls and room regions fall back to low-confidence heuristics (the agent is told to check them visually). The model's code and weights are CC BY-NC 4.0: non-commercial use only. Raster pages without DPI metadata have no scale yet, so they get no 3D model. Schema changes rely on `create_all` (no migrations).

## Checks

`make check` runs what CI runs: ruff format and lint, mypy and pytest for the backend; prettier, eslint, tsc, vitest and a build for the frontend; and the 600-line file limit. Team rules are in [RULES.md](RULES.md).
