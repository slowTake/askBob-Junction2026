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

## Run it

**With Aiven** (shared setup; first follow [docs/aiven-setup.md](docs/aiven-setup.md)):

```bash
export AIVEN_PROJECT=<project> AIVEN_PG_SERVICE=<pg-service> AIVEN_VALKEY_SERVICE=<valkey-service>
source scripts/aiven-env.sh        # exports DATABASE_URL / VALKEY_URL for this shell only
export ANTHROPIC_API_KEY=...       # or keep it in the keyring; see aiven-setup.md
make up                            # UI on http://localhost:8080, API on :8000
```

**Offline**, with local Postgres and Valkey containers: `make up-local`.

**Without Docker** (fastest edit loop; needs `uv`, Node 22 and `tesseract` installed):

```bash
export DATA_DIR=$PWD/.local/data   # plus DATABASE_URL, VALKEY_URL, ANTHROPIC_API_KEY
make dev-api      # terminal 1: API with reload on :8000
make dev-worker   # terminal 2: ingest worker
make dev-web      # terminal 3: UI on :5173, proxies /api to :8000
```

Docker needs the daemon running and your user in the `docker` group (`sudo systemctl start docker`, `sudo usermod -aG docker $USER`, then log in again).

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
backend/eval/  question set runner: accuracy and verified-rate against a running API
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
| Measuring accuracy | put Stoa's example questions in a JSONL file and run `uv run python -m eval.run_eval file.jsonl` |

**Current limits:** for raster images, wall detection and room regions are heuristics with low confidence (the agent is told to check them visually). Raster pages without DPI metadata have no scale yet, so they get no 3D model. Schema changes rely on `create_all` (no migrations).

## Checks

`make check` runs what CI runs: ruff format and lint, mypy and pytest for the backend; prettier, eslint, tsc, vitest and a build for the frontend; and the 600-line file limit. Team rules are in [RULES.md](RULES.md).
