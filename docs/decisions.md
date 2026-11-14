# Decision log

Product, data and engineering decisions, numbered `D-NNN`. Add the next number, an index row and an entry in the same PR as the change. Never rewrite an entry; supersede it with a new one and mark the old one as superseded.

| ID    | Date       | Decision                                            | Status   |
| ----- | ---------- | --------------------------------------------------- | -------- |
| D-001 | 2026-11-14 | Adopt the Lease Loop engineering rules, stack-neutral | Accepted |
| D-002 | 2026-11-14 | Track work in GitHub issues with one board            | Accepted |
| D-003 | 2026-11-14 | Stack: FastAPI + RQ worker, React/Vite, Docker Compose | Accepted |
| D-004 | 2026-11-14 | A canonical building model with provenance; IFC is an export | Accepted |
| D-005 | 2026-11-14 | Aiven for PostgreSQL and Aiven for Valkey; no Kafka/OpenSearch yet | Accepted |
| D-006 | 2026-11-14 | Q&A agent answers only from tools, with server-checked citations | Accepted |
| D-007 | 2026-11-14 | UI follows DESIGN.md; highlights by dimming, not colour | Superseded in part by D-012 |
| D-008 | 2026-11-14 | CI enforces RULES.md; local git hooks come later | Accepted |
| D-009 | 2026-11-14 | Kimi K3.1 Pro on Verda as a secondary LLM; keys in keyrings | Accepted |
| D-010 | 2026-11-14 | A document is never left queued without a job | Accepted |
| D-011 | 2026-11-14 | Demo video pipeline in `demo-video/`, outside tests and CI | Accepted |
| D-012 | 2026-11-14 | Drafting-table theme with a dark mode; drawings stay paper | Accepted |
| D-013 | 2026-11-14 | Fit a missing page scale from printed dimensions; two must agree | Accepted |
| D-014 | 2026-11-14 | Exact CAD/vector geometry first; pixel heuristics last | Accepted |
| D-015 | 2026-11-14 | Every format becomes IFC; one IFC indexer feeds the app | Accepted |
| D-016 | 2026-11-14 | Floor plans are the interactive surface; 3D only for IFC | Accepted |
| D-017 | 2026-11-14 | Ingest never leaves a document waiting for a job that is gone | Accepted |

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

## D-003: Stack: FastAPI + RQ worker, React/Vite, Docker Compose

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** The core libraries for drawings are Python-only or Python-first: ifcopenshell (IFC), PyMuPDF (PDF), OpenCV and Tesseract (raster). Ingesting a large drawing takes seconds to minutes, too long for a web request.

**Decision:** Python 3.12 backend: FastAPI for the API, an RQ worker on the same image for ingestion. Frontend: React 19 + Vite + TypeScript, three.js for 3D. Docker Compose runs UI (nginx), API and worker. uv and npm lockfiles pin every dependency. TypeScript stays on 6.0 because typescript-eslint does not support 7 yet.

**Consequences:** One language for all drawing logic. The API and the worker share a file volume, so they must run on the same Docker host until storage moves to S3/R2.

## D-004: A canonical building model with provenance; IFC is an export

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** The challenge asks for answers that are correct and that show where in the drawing they came from. IFC can't easily say "this wall came from pixels 120–180 on page 2", and asking a model to read pixels at answer time is what general-purpose AI gets wrong.

**Decision:** Every reader (IFC, PDF, image) writes the same tables: documents, pages, elements. Every element keeps its provenance (page bounding box or IFC GlobalId), its `source` (ifc, pdf_text, ocr, derived) and a `confidence`. From drawings with a known scale we also write an IFC file. Each product carries a `Bob_Provenance` property set and links back to its 2D element via the GlobalId.

**Consequences:** The same question works on any format. Answers can be checked in 2D and 3D. Adding a format means writing one reader. Schema changes use `create_all` (no migrations) during the hackathon.

## D-005: Aiven for PostgreSQL and Aiven for Valkey; no Kafka/OpenSearch yet

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** We want managed services wherever they help, and the free Aiven plans cover what we need.

**Decision:**
- **PostgreSQL** holds the building model, the Q&A log (for evaluation) and two extensions: `pg_trgm` for fuzzy label search and `pgvector`, ready for embeddings.
- **Valkey** runs the ingest job queue (RQ), the live progress events (pub/sub, streamed to the browser over SSE) and a cache of answers keyed by question and document version.
- Not adopted for now: Kafka and OpenSearch would add moving parts without solving a problem we have; Postgres covers search at our scale. Revisit if ingest volume or search quality demands it.
- Local Postgres and Valkey containers exist only as an offline fallback (`make up-local`). Connection strings come from `scripts/aiven-env.sh` at runtime and are never written to a file.

**Consequences:** Creating the Valkey service follows the team rule in `docs/aiven-setup.md` (announce it first). Aiven has no object store, so files stay on a Docker volume.

## D-006: Q&A agent answers only from tools, with server-checked citations

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Answers must be verifiable. A model that cites things it never looked at is not.

**Decision:** Claude Opus 5.5 (`claude-opus-5-5`, effort `high`, adaptive thinking) runs a manual tool loop with read-only tools: `find_elements`, `get_element`, `view_region` (returns a crop of the drawing as an image) and `measure_distance` (only on pages with a known scale). The final answer is structured JSON (`output_config.format`) with citations. The server accepts a citation only if it points at an element or region that a tool actually returned in this conversation, and marks the answer "verified" only when all citations pass. Server-side refusal fallbacks are on (`fallbacks: "default"`). We use a manual loop rather than the SDK's beta tool runner because we validate inputs ourselves, return images from tools, stream each step to the UI and record evidence.

**Consequences:** Every answer is traceable or visibly marked as unverified. Model choice and effort are environment settings (`CLAUDE_MODEL`, `CLAUDE_EFFORT`), so we can trade cost for quality without code changes.

## D-007: UI follows DESIGN.md; highlights by dimming, not colour

**Date:** 2026-11-14 · **Status:** Superseded in part by D-012 (styling, font, 3D highlight colour, answer card); the spotlight still applies

**Context:** DESIGN.md defines a black-and-white system with pill controls and no accent colour. Drawings are themselves black lines on white, so a black outline alone gets lost.

**Decision:** Tokens from DESIGN.md live in `frontend/src/styles/tokens.css`. Inter is the font, as DESIGN.md recommends in place of its proprietary faces. A cited region is shown with a spotlight: the rest of the page is dimmed and the region is ringed. In 3D, the cited element turns black. The latest answer uses the polarity-flipped (black) card.

**Consequences:** No new colours to justify. Changes to the design start in DESIGN.md.

## D-008: CI enforces RULES.md; local git hooks come later

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** D-001 deferred enforcement until a stack was chosen.

**Decision:** GitHub Actions runs format, lint, type check, tests and build for both apps, the 600-line file check, conventional commit messages on PRs, and a Docker build. `make check` runs the same checks locally.

**Consequences:** Local pre-commit hooks (secret scan, formatting, commit-message check) are still to do; until then run `make check` before pushing.

## D-009: Kimi K3.1 Pro on Verda as a secondary LLM; keys in keyrings

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** The Q&A agent runs on Claude Opus 5.5 through the Anthropic SDK (D-006). Every team also gets Verda credits, and Verda's inference API serves Kimi K3.1 Pro. Verda speaks only the OpenAI Chat Completions and Responses APIs: `POST /v1/messages` returns 404, so the Anthropic client can't be pointed at it. A test call to Kimi K3.1 Pro worked (HTTP 200, about 1.2 s).

**Decision:** Claude stays the Q&A agent. Kimi K3.1 Pro on Verda (`kimi-k3-1-pro`, `https://inference.verda.com/v1`, via an OpenAI SDK) is available for side tasks where the Anthropic-only features of D-006 aren't needed, such as cheap bulk calls or experiments, and for the Verda prize. Each person creates their own Verda key in our project and keeps it in their OS keyring, passing it to one process at a time. The deployed app reads any key from the host's secret settings. No key goes in the repo, a `.env` file or chat. Setup in `docs/verda-setup.md`.

**Consequences:** Code that uses Verda has its own OpenAI-compatible client, separate from the Anthropic one; moving the Q&A agent itself to Verda would mean a rewrite and a new decision superseding D-006. Verda lists no embedding model, so embeddings need a separate decision.

## D-010: A document is never left queued without a job

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Upload and reingest commit the document as `queued` and then enqueue the ingest job in Valkey. When Valkey was unreachable the API answered 500 and the row stayed `queued` forever: no job existed, and the UI showed "Processing…" with no way out (issue #9).

**Decision:** If the job cannot be enqueued, the API undoes the state change and answers `503` with the envelope error `queue_unavailable`. An upload is rolled back completely (row and stored file removed), so the user simply uploads again; a reingest puts the previous status back. We keep "commit, then enqueue" rather than "enqueue, then commit", because a worker could otherwise pick the job up before the row exists.

**Consequences:** `queued` always means a job is waiting. A crash between the commit and the enqueue can still strand a row; a sweeper for that is not worth it at hackathon scale. Documents that were stranded before this change need a manual reingest or delete.

## D-011: Demo video pipeline in `demo-video/`, outside tests and CI

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Junction requires a video pitch of "not a second longer than 2 minutes", enforced strictly. We want anyone on the team, or an agent, to rebuild the video quickly when the app changes, and the length to be checked by a command rather than by memory.

**Decision:** A separate uv project in `demo-video/` builds the video from one file, `video.yaml` (settings and segments). `make plan` checks the word budget, `make check` fails a final video over 115 s (target 110 s, Junction's limit 120 s, title cards included), and voice, recording, assembly and review steps are added as stubs to fill in. The pipeline is not part of the app: it is **exempt from RULES.md §3 (tests) and §8 (CI)**, and is not in `make check` or the CI workflow. RULES.md §5 still applies through the repo-wide file-size check, and §6 still applies: API keys come from the OS keyring per D-009, and media in `demo-video/out/` is git-ignored.

**Consequences:** A broken pipeline can't block an app PR, but nothing catches its bugs except running it. Every product shot in the video must be a real recording of the app.

## D-012: Drafting-table theme with a dark mode; drawings stay paper

**Date:** 2026-11-14 · **Status:** Accepted · **Supersedes in part:** D-007

**Context:** The Uber-derived DESIGN.md (pill buttons, 52 px hero, black answer card, no accent) made the app read as a consumer product. We compared three mockups and chose Direction A (engineering-software look) for light, with the dark panels of Direction B. We keep the name bobBuilder for now.

**Decision:** DESIGN.md is replaced by our own system: IBM Plex Sans and Plex Mono, square corners, hairline rules, a dark app bar and one blue accent. Status colours (ok, warn, danger) are separate from the accent. A dark theme follows the OS and can be toggled in the app bar; the choice is stored in `localStorage` under `bob.theme` and applied before first paint. Scanned sheets stay white paper in both themes, and marks drawn on them keep one blue. The D-007 spotlight stays, with the ring in the accent colour; in 3D the cited element turns blue instead of black. Only the latest answer is a card.

**Consequences:** Components must use tokens only, so a theme change is a token change. The one exception is the 3D viewer: three.js materials can't read CSS variables, so `ModelViewer.tsx` repeats the `paper-mark` blue and keeps it in both themes. The clean redraw (#54) is the only view that inverts in dark mode. The highlight tool (#55) will revisit how cited regions are drawn.

## D-013: Fit a missing page scale from printed dimensions; two must agree

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** 614 of the 680 raster drawings in the preview have no DPI metadata (#40), so the reader never set `mm_per_px`: no areas and no 3D footprints for them. Pages with a DPI but no `1:N` note had the same gap.

**Decision:** When a page has no DPI and scale note, `annotate_page` fits the scale from its dimension labels: for each label it finds the dimension line beside it, measures the line between the ticks either side (extension lines, slashes or dots), and divides the printed millimetres by that length. A scale is kept only when **at least two labels agree within 3%**; the median of the agreeing group is used. One label alone is never trusted, because a single OCR misread would give confidently wrong areas, and an unknown scale is safer than a wrong one. The fallback runs on every page, PDFs included. Page meta records `scale_method` (`dpi`, `dimension_fit` or none) and, for a fit, `scale_support` (how many labels agreed). Scale bars are not handled yet.

**Consequences:** Plans with dimension chains get areas and footprints; plans without printed dimensions (many CubiCasa sheets, some marked "not to scale") still have no scale. Upside-down sheets are not read, because OCR only tries 0° and 90°. The 3% and two-label thresholds are constants in `app/domain/scale_fit.py` and may need tuning on real plans.

## D-014: Exact CAD/vector geometry first; pixel heuristics last

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** The 3D model from a Swiss PDF was unusable: walls were guessed from pixels (hatched, rotated walls broke the heuristic) and Swiss room names weren't recognised. The dataset ships most Swiss drawings as DXF too, with named layers (`WALL`, `DOOR`, `WINDOW`, `ROOM_OUTLINE`, `ROOM_TEXT`, `UNIT_OUTLINE`), and its PDFs draw hatched walls as clip paths.

**Decision:** Read geometry from the most exact source available, in this order:
1. **DXF:** layers by name, in real units.
2. **PDF vector layer:** hatched clip paths become walls, and the printed room number and area are linked to each room name.
3. **Pixels:** only when neither of the above exists.

Counting and area rules found in the data live in tested pure functions:
- A door is a swing arc, and a double door's two arcs share one endpoint.
- A window is a closed frame.
- A shaft is an unnamed room under 0.55 m mean width.
- Net area covers numbered rooms, excluding shafts and outdoor spaces.

The agent gets these rules as the `sum_room_areas` tool. A traced room outline is dropped when it disagrees with the printed area by more than 15%, or when it reaches the page edge.

**Consequences:** Scored against the dataset's English swiss_dwellings questions:

| Question type | DXF | PDF |
|---|---|---|
| Room-name counts | 99.5% | 99% |
| Room areas | 100% | 35% |
| Apartments | 100% | 100% |
| Doors | 97% | 0% |
| Windows | 100% | 0% |
| Area totals | 92–100% | 34–37% |

The PDF path still lacks doors, windows and apartment membership. Fixtures (WC, washbasin, bathtub, shower) are not classified yet.

## D-015: Every format becomes IFC; one IFC indexer feeds the app

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Each format had its own path into the database, so "same shape, same accuracy" depended on every reader agreeing by hand. We also want models that open in BIM tools, and an agent that can highlight elements in 3D for any format.

**Decision:**
- Every non-IFC upload (DXF, DWG, PDF, SVG, PNG/JPEG/TIFF/WebP/BMP/GIF) is read into elements and written as an **IFC4 model**. IFC uploads are already one.
- A single IFC indexer turns any IFC into the stored elements, and the 3D mesh comes from the same IFC. Elements, mesh and downloads therefore share GlobalIds.
- Drawing findings carry a `Bob_Element` property set (kind, source, confidence, page, box, properties), so the round trip loses nothing. The Swiss scores are identical before and after the round trip.
- Kinds map to standard IFC classes, defined in both directions in `domain/model_rules.py`: apartments are `IfcZone`, known fixtures are `IfcSanitaryTerminal` with a type, and text is `IfcAnnotation`.
- Counting rules (nested parts, IFC2X3 types, units) live in the indexer, so they apply to every format.
- **Sturdiness:**
  - Known failures raise `ReaderError` with a user-facing message (damaged file, password-protected PDF, no DWG converter, empty drawing).
  - A model that can't be meshed still answers questions.
  - Big models are trimmed to a triangle budget for the browser (fabric first), and the mesh is stored gzipped.
  - DXFs whose layer names mean nothing fall back to vision on the rendered page, with the DXF's exact text and scale.
- **DWG** needs LibreDWG `dwg2dxf` or the ODA File Converter. Debian doesn't package LibreDWG, so the container has neither for now, and DWG uploads ask for a DXF export.

**Consequences:** The pipeline is tested end to end per format (`ingest/pipeline_test.py`) and was run on a sample of every source in the dataset preview: 27 of 28 files processed; the DWG failed by design (no converter installed). The shape is documented in `docs/model.md`.

## D-016: Floor plans are the interactive surface; 3D only for IFC

**Date:** 2026-11-14 · **Status:** Accepted · **Refines:** D-007, D-015

**Context:** For a drawing, the 3D view was an extrusion with invented heights (walls 2.6 m, doors as floor markers). It added nothing a plan doesn't show, hid the useful information (room names, numbers, areas, dimensions) and was clumsy to use. Engineers read plans.

**Decision:**
- **Drawings** (DXF, DWG, PDF, SVG, images) get no 3D view and no mesh. Their IFC still carries extruded geometry, for BIM tools.
- **IFC models** keep their 3D view. They also get **floor plans, one page per storey**, drawn from the model's own geometry (`bim/ifc_plans.py`), with room names, numbers and areas. The built-in ifcopenshell drawing module produced unusable output in 0.9, so we draw the plans ourselves.
- Every drawn element knows its page and box, so **the plan is interactive for every format**:
  - hover a room to see its name, number and area
  - click any element for its details
  - toggle layers (rooms, doors and windows, fixtures, walls, text)
- **The agent drives the plan** with two tools, which stream `view` events to the UI while the answer arrives. The answer stores its views, so cached answers and "Show on plan" replay them.
  - `highlight` lights up the elements an answer is about.
  - `measure_between` draws a measured line between two elements, centre to centre, plus the nearest-edges distance.

**Consequences:** Ingest is faster for drawings (no meshing). The 3D tab appears only when a document has a real model. The agent tools are covered by schema tests; the measurement geometry is a tested pure function.

## D-017: Ingest never leaves a document waiting for a job that is gone

**Date:** 2026-11-14 · **Status:** Accepted · **Refines:** D-010

**Context:** Documents stayed "Queued" or "processing" forever, with nothing working on them. Causes seen or possible: forked job processes shared the worker parent's database connection, so after a few jobs the first write of a job failed with `DuplicatePreparedStatement` (#56), and that write sat outside the job's error handling; Valkey lost its queue on a restart; a worker died mid-job. D-010 had accepted stranded rows as "not worth a sweeper".

**Decision:**
- Every forked process starts with an empty connection pool (`os.register_at_fork` in `app/db.py`), so job processes never share the parent's server session.
- The whole job runs inside its error handling; any failure marks the document `failed` with a reason, and recording the failure never raises.
- RQ safety nets mark in-flight documents failed: a failure callback (also run for jobs abandoned by a dead worker: `ingest_interrupted`) and a killed-work-horse handler (out of memory: `ingest_killed`). Maintenance runs every 60 s, so a dead worker's job is noticed within about 2.5 minutes.
- On start, the worker queues again every `queued` or `processing` document that no queued or running job refers to (older than 60 s, so a fresh upload is never doubled).
- `/api/health` reports `ingest_workers`, so the UI can say that no worker is running instead of a silent "Queued". `ok` still covers only Postgres and Valkey: without a worker the API works and uploads wait.

**Consequences:** A document is never stuck: it finishes, fails with a reason the user can act on, or is picked up again when a worker starts. A document interrupted by a restart is marked failed rather than retried automatically, so a file that crashes the whole worker can't loop forever.
