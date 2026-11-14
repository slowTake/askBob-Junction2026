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
| D-009 | 2026-11-14 | Kimi K3.1 Pro on Verda as a secondary LLM; keys in keyrings | Partly superseded by D-020 |
| D-010 | 2026-11-14 | A document is never left queued without a job | Accepted |
| D-011 | 2026-11-14 | Demo video pipeline in `demo-video/`, outside tests and CI | Accepted |
| D-012 | 2026-11-14 | Drafting-table theme with a dark mode; drawings stay paper | Accepted |
| D-013 | 2026-11-14 | Fit a missing page scale from printed dimensions; two must agree | Accepted |
| D-014 | 2026-11-14 | Exact CAD/vector geometry first; pixel heuristics last | Accepted |
| D-015 | 2026-11-14 | Every format becomes IFC; one IFC indexer feeds the app | Accepted |
| D-016 | 2026-11-14 | Floor plans are the interactive surface; 3D only for IFC | Accepted |
| D-017 | 2026-11-14 | Ingest never leaves a document waiting for a job that is gone | Accepted |
| D-018 | 2026-11-14 | The plan is a pan/zoom canvas; nothing that appears moves it | Superseded in part by D-024 |
| D-019 | 2026-11-14 | Answers carry a numeric value; the eval scores it by question type | Accepted |
| D-020 | 2026-11-14 | The Q&A agent can run on Kimi K3.1 Pro on Verda (`LLM_PROVIDER`) | Accepted |
| D-021 | 2026-11-14 | A citation's box is the element's extent; the printed name is the fallback | Accepted |
| D-022 | 2026-11-14 | A floor-plan model (CubiCasa5k) in its own `vision` service reads raster plans | Accepted |
| D-023 | 2026-11-14 | The `vision` service works within a fixed pixel budget, whatever the upload | Accepted |
| D-024 | 2026-11-14 | Fit frames the drawing's ink; agent highlights keep the plan fitted; one conversation per document | Superseded in part by D-035 |
| D-024 | 2026-11-14 | Raster rooms are traced from the drawing's lines; RapidOCR reads the text | Accepted |
| D-025 | 2026-11-14 | The server counts: `count_elements`, not the model adding up search results | Accepted |
| D-026 | 2026-11-14 | The agent knows its step budget, and its last turn is the answer | Accepted |
| D-027 | 2026-11-14 | Upscale is one on-demand vision pass per page; the redraw shares the page's coordinates | Accepted |
| D-028 | 2026-11-14 | On raster images a model redraws the whole sketch in a draw, compare, correct loop; nothing is measured | Superseded in part by D-029, D-035 |
| D-029 | 2026-11-14 | Sketch check rounds show the draft in red over the photo, and the model is told where the ink is | Accepted |
| D-025 | 2026-11-14 | Bound optional raster analysis and make Claude startup explicit (#106) | Accepted |
| D-026 | 2026-11-14 | Room highlights require boundaries traced from the drawing (#103) | Accepted |
| D-027 | 2026-11-14 | Match raster drawings to uploaded native DXF room boundaries (#108) | Accepted |
| D-030 | 2026-11-14 | Matched CAD rooms survive the redraw integration (#108) | Accepted |
| D-031 | 2026-11-14 | Claude omits unused tool filters to stay within strict-schema limits (#111) | Accepted |
| D-032 | 2026-11-14 | `make up-*` start in the background and smoke-check the stack (#107) | Accepted |
| D-033 | 2026-11-14 | The UI's nginx finds the backend per request, at an address from `BACKEND_URL` (#107, #64) | Accepted |
| D-034 | 2026-11-14 | The demo runs on Aiven Runtime as one container: UI, API and worker (#116) | Accepted |
| D-035 | 2026-11-14 | One Export menu holds Download IFC, Download SVG and Print (#109) | Accepted |
| D-036 | 2026-11-14 | Every question reports what it used; the eval turns that into cost | Accepted |

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

**Date:** 2026-11-14 · **Status:** Partly superseded by D-020 ("Claude stays the Q&A agent")

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

## D-018: The plan is a pan/zoom canvas; nothing that appears moves it

**Date:** 2026-11-14 · **Status:** Superseded in part by D-024 (what 100 % means; agent views no longer fly the camera) · **Refines:** D-016

**Context:** The plan flickered: the hover card and banners were inserted above the drawing, so showing them pushed the plan down, the element slid out from under the cursor, and the card vanished again. Zoom stopped at "fit width", so a tall sheet never fit on screen. An agent highlight of one window only scrolled, so users had to zoom out to find it. Older answers were grey on grey, and the agent did not know what the user was looking at.

**Decision:**
- The page is moved by one CSS transform (a camera: scale and offset). Drag pans, the wheel zooms at the cursor, + − 0 keys and buttons zoom and fit. 100 % means the whole page fits; zoom goes from 25 % of that to 4 screen pixels per page pixel.
- Nothing that appears moves the drawing: banners and zoom controls float over it, and element details live in a fixed-height bar under it that keeps the last element pointed at.
- An agent view or a citation flies the camera to its elements once, framed with at least 20 % of the page around them; several highlighted elements get numbered badges in reading order, and every view the agent produced is a button on its answer.
- Each question carries the page on screen and the element the user selected ("Ask about this"), so the agent can resolve "this room" (`AskContextIn`, cache key includes it).
- The documents panel can be hidden; the choice is kept in `localStorage` (`bob.sidebar`). Every answer is full contrast; only steps and caveats are muted.
- Document status says why a document waits (including "no ingest worker is running"), the list re-reads when the event stream reconnects and polls while anything is in flight, and failed documents offer "Process again".

**Consequences:** Overlay sizes are multiplied by `--u` (one screen pixel in page pixels) so lines and labels look the same at every zoom in every browser. The element layer is memoised, so panning never redraws hundreds of shapes.

## D-019: Answers carry a numeric value; the eval scores it by question type

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** The dataset's `questions.jsonl` gives each question a `type` and scores counts exactly and areas, lengths and volumes within 2%; text answers are free-form (issue #41). Our eval accepted any number within 2% anywhere in the answer text, so "Room 2.01 is 15.61 m²" could pass on the room number, and a count of 13 passed for 13.2. The agent's answer was only free text, so there was no single value to score.

**Decision:** The agent's structured answer (D-006) gains `value` (one number in the unit the question asks for, or null) and `unit` (or null), and `/api/ask` returns both. The eval scores `value`: counts must be equal, area, length and volume within 2% relative. Text and other answers are not scored automatically; the report lists them separately. The answer cache key includes an answer-format version, so cached answers from before a payload change are not served. Eval runs upload a sample of the dataset to a local stack (`make up-local`) by default, not to the shared Aiven database.

**Consequences:** One accuracy number per run, split by source and type, that matches the challenge's rules. A correct answer with a null `value` counts as wrong, which also measures whether the agent fills the field. Text questions (265 of 7,990 in the preview) need a manual or model-graded check later.

## D-020: The Q&A agent can run on Kimi K3.1 Pro on Verda (`LLM_PROVIDER`)

**Date:** 2026-11-14 · **Status:** Accepted · **Supersedes:** the "Claude stays the Q&A agent" part of D-009

**Context:** Nobody on the team has a confirmed Anthropic key, so the agent and the eval can't run end to end. Everyone can create a Verda key (D-009). A capability probe of `kimi-k3-1-pro` on Verda (#51) found that it does strict function calling, JSON-schema `response_format` and image input (an `image_url` data URL, also in a user message after tool messages), and that it does not need its `reasoning_content` sent back. With tools **and** a `response_format` schema in the same request, it skipped the tools and answered at once with invented element ids.

**Decision:** `LLM_PROVIDER=anthropic|verda` (default `anthropic`) picks the model loop. The Verda loop (`app/qa/verda_agent.py`, OpenAI SDK) uses the same system prompt, tools, citation check, answer cache and `qa_log`, and emits the same `step`/`final` events and answer as the Claude loop of D-006. Its final answer is a `final_answer` tool call whose input is the answer schema, validated with the same `FinalAnswer` model, and every request sets `tool_choice: "required"`. `view_region` images go in a user message after the tool messages. The key comes from `VERDA_API_KEY`, passed from the keyring per D-009; a missing key gives `llm_not_configured`. Adaptive thinking, effort, refusal fallbacks and `cache_control` have no equivalent on this path. The answer-cache key and `qa_log.model` use the active model, so answers from the two providers never mix.

**Consequences:** Claude stays the default and the agent we demo. Eval scores on Kimi measure Kimi, not Claude. Behaviour the probe didn't cover, such as long multi-step runs and large images, is unknown until the eval runs on real drawings. The conversion code (`app/qa/openai_format.py`) is tested without network; a change in the answer schema reaches both loops through `ANSWER_SCHEMA`.

## D-021: A citation's box is the element's extent; the printed name is the fallback

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Clicking a citation about a room spotlit and framed only the room's printed name. In a walkthrough, 22 of 22 room citations were label-only, even for rooms whose outline the reader had found (#70). The room element's `bbox` is the box of its name, and the citation payload sent that box. The plan layer (D-016) already draws a cited room's outline by element id, but the spotlight and the camera frame still used the name's box.

**Decision:** A pure `element_extent` (`app/domain/extent.py`) decides where an element is: for rooms, the outline's bounds and polygon when `polygon_px` exists, otherwise the name's box; other kinds keep their own box. Every tool records element evidence through one builder, `element_evidence`, so `find_elements`, `get_element`, `highlight` and `measure_between` all give the same shape. The citation payload's `bbox` is the extent, and it adds `polygon`, `label_bbox` (only when the box is a name inside an outline) and `target` (`element`, `label` or `region`). The viewer cuts the spotlight out of the room's polygon, frames agent views and citations by the extent, and tags a label-only highlight as "Label only". `ANSWER_FORMAT` goes to 3 so cached answers in the old shape aren't served.

**Consequences:** Rooms with a found outline are framed as rooms with no re-ingest. Rooms without one stay "Label only" until their outline is found (#34).

## D-022: A floor-plan model (CubiCasa5k) in its own `vision` service reads raster plans

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** On PNG/JPG drawings and scanned PDF pages the readers only find OCR text, rooms flood-filled from their labels and low-confidence wall boxes. There are no door, window or fixture elements, so a question like "where is the exit?" gets the word EXIT highlighted instead of a door. Vector PDFs have exact walls and text but no doors or windows either (0% in the swiss_dwellings scores). We tested the pretrained CubiCasa5k model (#84) on dataset plans:
- On CubiCasa's own Finnish plans its door, window, WC and sink counts were mostly within one of the dataset answers.
- On a Swiss sheet, cropped to the drawing and enlarged 1.5×: doors 41/43, WCs 5/6, washbasins 3/3, bathtubs 2/3, windows 14/20.

**Decision:**
- **A separate `vision` service** (`vision/`) runs the model on CPU-only PyTorch. The worker sends it each page image over HTTP. The model is about 17M parameters, so a CPU is enough, and the backend image stays free of PyTorch.
- **Model code and weights are fetched when the image is built, not committed.** CubiCasa5k's code and weights are CC BY-NC 4.0: fine for this non-commercial challenge in a private repo, but they must not ship in a product without permission. Their post-processing file is also over our 600-line limit.
- **What the service does with a page:**
  - **Crop:** a framed sheet (a line spanning the page) is cropped to the drawing, so the title block and legend aren't read as fixtures.
  - **Scale:** framed sheets are enlarged 1.5×, and other images stay at 1×. This was measured on one Swiss floor (0.75× and 1× scored worse); a proper auto-scale is follow-up work.
  - **Network:** runs in overlapping tiles, so memory doesn't grow with page size. Full precision, because fp16 output crashed CubiCasa's door post-processing. One pass by default; `VISION_ROTATIONS=4` averages four rotated passes as in CubiCasa's notebook.
  - **Polygons:** CubiCasa's own post-processing turns the output into polygons, mapped back to original-image pixels.
- **What its output becomes:** the same elements the DXF reader produces, with `source: "vision"`.
  - **Doors and windows** become `door` / `window` (confidence 0.7).
  - **WCs, washbasins, sinks and bathtubs** become `fixture` with `subtype` `wc`, `washbasin`, `sink` or `bathtub`, so they map to `IfcSanitaryTerminal`. A sink inside a kitchen region is a `sink`; anywhere else it's a `washbasin`. Other objects are fixtures with `properties.object`.
  - **Rooms and walls:** on images and scanned pages, model rooms give OCR room labels their outline (replacing the flood fill), and model walls replace the pixel wall boxes. On vector PDF pages the model adds only doors, windows and fixtures; walls and text stay from the PDF.
- **Fallback:** if the service is not configured, unreachable or fails, ingest runs exactly as before, and the page records `meta.vision` as `unavailable` or `failed`.

**Consequences:**
- Raster plans get doors, windows and fixtures the agent can count, highlight and cite.
- A Swiss sheet takes a minute or more on CPU, because CubiCasa's post-processing is slow at 1.5×. Ingest runs in the background with progress events, so this is acceptable for now.
- Windows on Swiss drawings stay weak until the model is fine-tuned on Swiss data. The swiss_dwellings DXFs give exact labels for their PNGs.
- Auto-scale, door-to-room connections (exits) and a faster polygon step are separate issues.

## D-023: The `vision` service works within a fixed pixel budget, whatever the upload

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** A 10200 × 6600 px US piping plan took the whole machine down. The backend shrinks images to 8000 px wide, and D-022 then cropped the framed sheet and enlarged it 1.5×, so the network read 11304 × 7347 = 83 Mpx. Its output is 44 floats per pixel, kept for the whole page because CubiCasa's polygon step needs them: 14.6 GB for one copy, on a 15 GB laptop.

**Decision:**
- **Scale from a pixel budget.** The scale is D-022's desired zoom (1.5× for framed sheets, 1× otherwise), capped so the network reads at most 16 Mpx. Small drawings are still enlarged; big sheets are shrunk. If the cap would push the scale below 0.35×, walls would be about a pixel thick, so the page is skipped: `method: "skipped_too_large"`, with no elements.
- **Labels-only path for anything over 4 Mpx.** Each tile's 44 channels are reduced at once to two bytes per pixel, the room class and the object class, and each pixel comes from the one tile whose middle covers it. Rooms, walls and objects are traced from those label maps. Door and window pixels count as wall when tracing rooms, so two bedrooms joined by a doorway stay two rooms.
- **CubiCasa's detailed polygon step** (all 44 channels, snapped corners) only runs on inputs up to 4 Mpx. That covers CubiCasa-style plans and the cropped Swiss A4 sheets.
- **Memory cap:** the `vision` container is limited to 6 GB. If a page still needs more, only that container is killed, and the backend falls back to pixel heuristics (`vision: unavailable`/`failed`).

**Consequences:**
- Memory no longer grows with the upload: labels for a 16 Mpx page are 32 MB, and the network works one 1024 px tile at a time.
- Big sheets get rougher outlines (traced regions instead of snapped polygons), and two touching objects of one class can merge into one.
- Very large or dense sheets are skipped rather than read badly.
- The model still runs on drawings that aren't floor plans, such as piping plans, and finds nonsense there. Detecting those is follow-up work.

## D-024: Fit frames the drawing's ink; agent highlights keep the plan fitted; one conversation per document

**Date:** 2026-11-14 · **Status:** Superseded in part by D-035 (where Download IFC shows) · **Supersedes in part:** D-018

**Context:** Fit framed the whole sheet, so scans and PDF pages showed wide paper margins around a small drawing. Framing the detected elements instead failed on sparse scans (one OCR'd letter made Fit zoom onto it). Agent highlights zoomed the plan in after every answer, with a "Shown by the assistant" banner on top. The chat kept one conversation for all documents, so switching drawings mixed answers about different plans (#83).

**Decision:**
- **Fit frames the drawing's ink.** The browser samples the page image (longest side 1024 px), groups dark pixels into connected pieces and keeps every piece with at least 10 % of the largest one's ink, so logos, footers and specks set apart from the plan drop out while several plans on one sheet are all kept. A blank or unreadable page fits the whole sheet. **100 % now means "as Fit shows it"**, and zoom limits are relative to that (this replaces D-018's "100 % means the whole page fits").
- **Agent highlights don't move the camera.** The plan fits the window with the highlight drawn on it and no banner; ⌖ zooms to it on demand. A source the user clicks in an answer still flies to it with its verified badge (this replaces D-018's "an agent view … flies the camera").
- **One conversation per document.** Picking a document in the list shows its conversation, a new upload starts empty, and an answer streams into the conversation it was asked in even if the user switched. Deleting a document forgets its conversation. The New conversation button is removed. Conversations live in the browser tab's memory only.
- The chat shows one status line (the agent's latest step) while it works, and scrolls to the end when a question is asked or answered.
- **Asking pins the conversation.** Until a document is picked in the list the chat follows the open document; once a question is asked, the chat stays on that conversation even when the agent or a clicked source opens another document.
- **A conversation's questions are about its document**, even when an answer has opened another one: the page on screen and selected elements are sent only when they belong to it, and the scope label names it ("Ask about these N" moves the chat to the selected elements' document). An answer's views move the plan only while its conversation is on screen; otherwise they wait as buttons on the answer. Agent highlights have a Clear button next to ⌖, and Download IFC also shows above the plan while the documents panel is collapsed.
- **Shift+click selects several elements** on the plan (a plain click still selects one). "Ask about these N" sends them all: `AskContextIn.element_ids` (up to 20; the single `element_id` still works), and the agent is told the user selected these elements, so "these" and "them" refer to them. One selected element keeps the old wording and answer-cache key.
- **Answers are a summary line plus lists.** The agent leads with one short sentence, then groups ("Lower floor:") and "- " items, and puts how it got the answer in `caveats`; the chat lays this out as headings and bullet lists (`lib/answerText.ts`, rendered as elements, never HTML). `ANSWER_FORMAT` 4 keeps older one-paragraph answers out of the cache.

**Consequences:** Fit needs no backend change or re-ingest. A scan with a dark scanner border fits the whole sheet, as before. A reload loses the conversations. With no "New conversation" button there is no way to cancel a slow answer except a reload; a Stop button is the natural follow-up if that matters.

## D-025: Bound optional raster analysis and make Claude startup explicit

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #106

**Context:** One raster job waited over ten minutes for the vision service, blocking later uploads. A failed image request left the viewer saying Loading forever, and the Docker backend had no Anthropic key.

**Decision:** Vision enrichment waits at most 90 seconds per page by default, configurable with `VISION_TIMEOUT_S`, before using the existing heuristic fallback. Raster readers emit progress before OCR, vision and annotation; transparent PNGs are composited onto white paper. Document API requests and viewer image loads stop waiting after 30 seconds, with a retry for failed images; uploads allow 120 seconds. `make up-claude` reads credentials from the environment, the OS keyring, or hidden terminal input and starts the local stack with the selected provider. It fails clearly without credentials in noninteractive use.

**Consequences:** Slow CPU vision may produce fewer detected objects when it exceeds the budget. The vision server may finish its computation after its client disconnects. Keys stay outside the repository; existing containers must be recreated to apply changed credentials. Image retries reload the image without reprocessing the document.

## D-024: Raster rooms are traced from the drawing's lines; RapidOCR reads the text

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** On raster pages (PNG/JPG, scanned PDFs), a printed room label got its outline either from the floor-plan model (D-022), whose rooms are built from rectangles and merge neighbours (two bedrooms became one), or from a flood fill that leaks through doorways. Tesseract read only 42% of the Swiss room numbers at 150 DPI. A prototype (#103) on 8 Swiss preview floors (289 rooms), scored against their DXFs with the physical scale (DPI + printed "1:100") and no tuning against the answers:

| | Tesseract + model rooms | RapidOCR + traced rooms |
|---|---|---|
| Room numbers read | 42% | 86% |
| Room found as its own room | – | 66% |
| Area within 5% of the DXF | – | 38% |

**Decision:**
- **Rooms come from the drawing's own lines,** as CAD "boundary" tools find them:
  - **Lines:** stroke centre lines (skeleton) plus the outlines of wall bands, closed over their hatching.
  - **Faces:** Shapely/GEOS extends near-touching ends, splits lines at crossings and finds every enclosed face (`polygonize`).
  - **Which faces count as rooms:** page-sized and thin faces (wall interiors, hatching) are dropped. A label goes to the largest face around it that holds no other room's label. A face that touches only one room and is smaller than it (a counter, a tub) is part of that room.
  - **Edge:** the outline is moved 2 px (at 150 DPI) out onto the wall face.
- **Outline sources for a printed room label,** in order: traced face, then model room, then flood fill. The printed-area check applies to all of them.
- **OCR:** RapidOCR (PaddleOCR's text detector and recogniser on ONNX Runtime; the models ship in the wheel) reads raster text in tiles. Tesseract stays as the fallback.

**Consequences:**
- Labelled rooms on raster plans follow their walls.
- About a third of rooms still leak through doorways drawn without a door swing, or lose part of their area to fixtures the rules don't absorb.
- Because the doorway line itself isn't drawn, a door's swing area counts toward the room on the other side of the door.
- Closing doorways fixes both and is the next step.
- OCR takes about 8–15 s per Swiss sheet on CPU.
- RapidOCR's recogniser has no accented letters ("Pièce" reads as "Piece"), so room names are now matched without accents.
- The app's own image reader, scored with `eval/swiss_rooms.py` on the same 8 floors: 70% of rooms named, 66% outlined, 36% with the area within 5% of the DXF.

## D-025: The server counts: `count_elements`, not the model adding up search results

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Counts are 76% of the preview questions (6,076 of 7,990). The agent had no counting tool, so it listed elements with `find_elements` and counted the list. That tool returns at most 50 results, so every count over 50 was wrong (the Maleva IFC model has 846 walls), and smaller counts depended on the model counting a JSON list (#93). (D-022 and D-023 went to the vision service, D-024 to #92.)

**Decision:** A `count_elements` agent tool, like `sum_room_areas` for areas. The rules are a pure `count` (`app/domain/counting.py`): elements of one required kind, narrowed by fixture `subtype`, room `category`, room `name` (exact, ignoring case and runs of spaces, so "Küche" doesn't count "Wohnküche"; it matches the printed label or the stored name, because an IFC space keeps its number in the label and its `LongName` in the name), IFC `storey`, document and page. An element missing a property never matches a filter on it. The tool returns the exact total, counts per page of each document and per storey, and lists the first 50 elements (by document, page and id, so the same question cites the same ones), which become citable evidence. The prompt sends every "how many" question to it. `ANSWER_FORMAT` goes to 5 (#92 took 4) so answers counted the old way aren't served from the cache.

**Consequences:** Counts are as good as the elements ingest stores. On IFC models they should now be right; on drawings, doors, windows and fixtures exist only once a detector produces them (#38, #88). Rules like "a doorway without a leaf doesn't count" belong to that detector, not to the tool. The agent still decides which kind and filters a question means.

## D-026: The agent knows its step budget, and its last turn is the answer

**Date:** 2026-11-14 · **Status:** Accepted · **Refines:** D-006, D-020

**Context:** The first eval on dataset drawings (#86, DeepSeek) ended 5 of 7 questions in `too_many_steps`: twelve model turns and no answer. Traces of three of them (#95) show three different causes, and one shared one:
- **IFC model facts** ("which software was used?"): the project, site and authoring application are not in the element store, so the model searched 20 times and never found them.
- **A door schedule:** the model read the table from image crops, a few rows at a time.
- **A raster plan:** it had no door elements (ingested without the vision service), so the model counted from image crops, at 15–100 s a turn on Verda.
- **Shared:** the model was never told how many turns it had, and nothing made it answer on the last one. Whether a run finished was chance: the schedule question failed in one run and answered on turn 9 in the next.

**Decision:**
- The question tells the agent its budget: `max_agent_turns - 1` rounds of tool calls, to answer as soon as it has the evidence, and, when a search finds nothing, to try other words or another `kind` and then say what is missing instead of searching on. It does not tell the agent that a miss means the documents lack the answer: the search matches text, so "kitchen" does not find a room labelled "Küche". With `max_agent_turns` of 1 the note says there are no tool calls.
- The last turn accepts only the answer, with a note saying so. On Verda the request names `final_answer` as the tool to call; Kimi and DeepSeek both honour that. On Claude the request sets `tool_choice` to `none`, because Opus 5.5 rejects a forced tool, and the note is a text block after the tool results, so nothing earlier in the conversation changes.
- An answer forced this way must say what is missing in `caveats` and set `confidence` to low. It is checked like any other answer: citations the tools never returned stay unverified.
- `too_many_steps` remains for a model that still gives no answer on its last turn.

**Consequences:** On the same five drawings, 8 of 8 non-raster questions now end with an answer (2 of 6 scored ones correct). A forced answer can be wrong; before, there was no answer. The three causes above are not fixed by this: they need model facts for IFC, a way to read schedule tables, and elements to count on raster plans (#93, D-022). The Claude path is covered by tests with a fake client only, since no one has an Anthropic key (D-020).
## D-026: Room highlights require boundaries traced from the drawing

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #103 · **Supersedes in part:** D-024 room-outline fallbacks

**Context:** The running app used Tesseract and model masks instead of the local prototype's RapidOCR and line tracing. It assigned one apartment-wide polygon to a bathroom and bedroom, and a jagged segmentation fragment to corridor 3.14. Model and flood-fill fallbacks can produce those shapes without proving a room boundary.

**Decision:** Use the prototype's RapidOCR and drawing-line tracing for room highlights. Every candidate must contain its own label and no other room name or unlinked room number. If no traced boundary passes these checks and the existing printed-area check, retain the printed label for citation. For raster pages, model masks and raw flood fills cannot substitute for room boundaries or create unnamed room fragments; model walls, doors and fixtures remain available. Exact-scale CAD renderings retain their existing closed-region fallback, subject to the same room-label checks.

**Consequences:** Some rooms have label-only citations when the drawing's lines do not establish their boundaries. On the two reported PNGs, the reader finds six and twelve separate traced rooms respectively, including the full corridor 3.14 instead of its small model fragment. Existing documents must be reprocessed to replace their stored geometry.

## D-027: Match raster drawings to uploaded native DXF room boundaries

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #108

**Context:** Raster line tracing cannot reliably recover all semantic spaces, especially an open kitchen beside a living area with no separating wall. The dataset supplies a corresponding DXF with exact room polygons and names. On the reported floor, OCR plus tracing located only part of the 17-room plan reliably.

**Decision:** Match uploaded raster/DXF files by filename stem, ignoring case. Use DXF text alignment and shared room numbers to fit a deterministic scale/rotation/translation. Require at least three labels, 75% agreement and a pixel residual within the page-size budget; reject ambiguous CAD revisions and polygons outside the raster. Preserve the raster image and map all native CAD rooms, names, areas and provenance into its page. The existing IFC export is built from these same rooms. Store the companion hash and alignment quality. Either upload order triggers a refresh once, including when a companion arrives during image processing; failed registration never loops. Native CAD companions bypass optional model segmentation. Existing raster behavior remains when no reliable companion exists.

**Consequences:** Exact semantic splits require the corresponding CAD file. OCR is used for registration, and can miss individual rooms without losing their CAD geometry. The reported 17-room drawing aligns on 16 labels with 0.39 px RMS error and retains all 17 separate spaces. A pair with fewer than three reliable shared numbers is left unmatched. Different DXFs with an identical filename stem are rejected rather than selecting a revision silently.

## D-027: Upscale is one on-demand vision pass per page; the redraw shares the page's coordinates

**Date:** 2026-11-14 · **Status:** Accepted

**Context:** Scanned pages are hard to read, and ingest misses walls, doors, windows and room names, so the agent can't cite them either (#82). #54 built a client-side redraw from the extracted elements, but its PR merged into a dead branch, and main has since moved to the pan/zoom canvas (D-016, D-018). Every vision call costs money, so it must not run on every ingest.

**Decision:** A **Redrawn** view next to **Original** in the plan toolbar. Before a page is upscaled it shows one centred **Upscale** button. `POST /api/documents/{id}/pages/{index}/upscale` sends the page image, resized so its longest side is `UPSCALE_MAX_SIDE` (1568 px), with the elements ingest found, to `UPSCALE_MODEL` (default `claude-haiku-5-5`) once. The pure rules in `app/domain/upscale.py` read its answer: only rooms, doors, windows and walls; confidence capped at 0.9 and dropped below 0.3; malformed or off-page entries skipped, never repaired; a candidate overlapping an element of the same group by half the smaller box is a duplicate and ingest wins (D-014). Added elements are stored with `source = "upscale"`; a room gets its box as an `approximate` outline and no area. The page row is locked during the call, and the result is cached in `page.meta.upscale` per document version and `UPSCALE_FORMAT`, so a second click is free. Each upscale bumps `document.meta.upscales`, which is part of the answer cache key, and the agent prompt says upscale boxes are approximate and must be checked like OCR.

The redraw (`frontend/src/lib/redraw.ts`, ported from #54) is an SVG in the page image's own pixel coordinates, drawn over the image and under the one overlay, so citations, highlights and the plan layer land on the same spot in both views. It is uniform on every format: walls filled (their DXF outline when stored, else their box), doors and windows as outlined boxes, room names bold with the computed area underneath, every other label at one size per page (1/100 of the page width, room names 1.5×) whatever the OCR box height. Unclassified OCR text below 0.6 confidence or without a letter or digit is left out; classified kinds are kept. What the upscale pass added is dashed in its own colour. The redraw stays white paper in both themes, like the original (D-012).

Small pages are enlarged, not sent as is: on colorful-34 (482 × 507 px) the native image gave Haiku too little to see and it returned nothing (1 412 tokens in), while the same page enlarged to 1491 × 1568 gave 22 candidates, 21 kept (4 103 in, 1 272 out).

**Consequences:** The redraw is only as good as extraction plus one vision pass: a vision model's boxes are approximate and can still miss elements, and doors and windows are boxes, not swing symbols. Low-resolution scans give tiny text at fit zoom. A re-ingest replaces the pages, so a page has to be upscaled again. The 0.6 text cut-off and the 1/100 text size are first guesses from one cubicasa page.

## D-028: On raster images a model redraws the whole sketch in a draw, compare, correct loop; nothing is measured

**Date:** 2026-11-14 · **Status:** Superseded in part by D-029 (how a check round shows the draft) and D-035 (where Download SVG and Print live) · **Refines:** D-027 (for raster image pages only)

**Context:** The demo shows a photo of a hand-drawn floor plan (a napkin sketch) turned into a clean plan with one button (#82). D-027's pass asks a small model once for what ingest *missed* and draws boxes. On a sketch, ingest's OCR and line detection are the unreliable part, so filling its gaps keeps its noise; boxes cannot show a door swing; and one unchecked answer has no way to notice its own mistakes. The owner's rules: one button; redraw, never invent (no measurement unless written on the sketch); a stronger, slower model is allowed for this path; output is the Redrawn view plus Download SVG and Print, no DXF.

**Decision:**
- **Which pages:** pages of raster image uploads (`Document.kind == "image"`). PDF, SVG, DXF, DWG and IFC keep D-027's gap-filling pass unchanged.
- **The model authors the whole plan.** `SKETCH_MODEL` (default `claude-opus-5-5`, effort `SKETCH_EFFORT`, default `high`, adaptive thinking, structured output, server-side refusal fallback) gets the photo at up to `SKETCH_MAX_SIDE` (2576 px) and returns walls (centre-line segments, outer or inner), doors (the opening on its wall, the hinge end, a point on the side it opens to), windows (a segment on the wall), rooms (the name exactly as written, a label point, an optional outline) and other written text. Ingest's elements are neither sent nor drawn.
- **Draw, compare, correct.** The pure rules (`app/domain/sketch*.py`) skip malformed, off-image and zero-length entries, then tidy the plan in page pixels: near-axis walls (within 8°) are made straight, wall lines and ends within 1 % of the page are joined, doors and windows are projected onto their wall. The tidied plan becomes shapes (walls cut at openings, an open door leaf with a quarter-circle swing, windows as a double line, labels at one size), rendered with Pillow at the size the model was sent. Rounds 2 to `SKETCH_MAX_ROUNDS` (default 3) send the photo, that render and the current plan; the model answers that they match or returns the whole corrected plan. The loop stops on a match, after the last round, or once `SKETCH_DEADLINE_S` has passed. A failed check round keeps the last good draft; a failed first round fails the request.
- **Stored as elements** with `source = "sketch"`, confidence 0.8, and their drawing in `properties` (page pixels), so the frontend draws exactly the shapes the model checked. Rooms get no area and no `value_mm`. Re-running replaces earlier `sketch` rows and any `upscale` rows of the page. The page caches the run in `meta.upscale` with `mode: "sketch"` and the rounds; `UPSCALE_FORMAT` goes to 3, and `PageOut.upscale` says the mode. The agent's prompt treats `sketch` elements as approximate and says a sketch has no scale.
- **No lock during the loop.** The endpoint claims the page under its row lock (a random token and the start time in `page.meta.sketch_run`), commits, runs the loop with no transaction open, then stores under the lock only if its claim stands and the document version is unchanged (else `redraw_superseded`). A second click meanwhile gets `redraw_running` at once instead of waiting minutes on a lock. Any failure drops the claim and stores nothing. A claim older than the deadline plus three call timeouts is stale, so a killed process can't block the page. The SDK may retry, since no lock is held.
- **No invented measurements**, closed at each place one could appear: the prompt forbids them; a number the model writes (free text with a digit, or a measurement-like part of a room name such as "3x4m" or "12 m²") is kept only when ingest's OCR read the same digits within 5 % of the page, otherwise dropped; the sketch redraw draws no scale bar whatever `mm_per_px` ingest derived (from file DPI and a scale note, or from fitted dimensions), and no room areas.
- **With `LLM_PROVIDER=verda`** the redraw fails with `sketch_needs_claude` instead of quietly using a weaker model.
- **Output:** the Redrawn view; while it is on screen the toolbar offers **Download SVG** (the on-screen svg with fixed light styles inlined, so it opens outside the app) and **Print** (a print stylesheet that prints only that sheet, fitted to the paper).

**Consequences:** A redraw takes minutes and costs a few strong-model calls (each round sends the photo, cached after the first, and a render). The plan is only as good as the model's reading: tidying straightens and joins but never adds a wall. OCR on handwriting is weak, so a dimension that really is written on a sketch can be dropped when OCR missed it; that loses information but never invents it. Line work in the redraw is relative to the page size, not to any real length. Not verified end to end against the real model when this was written (no API key was available).


## D-029: Sketch check rounds show the draft in red over the photo, and the model is told where the ink is

**Date:** 2026-11-14 · **Status:** Accepted · **Supersedes:** the check-round render in D-028

**Context:** In D-028 the model compared the photo with its draft as two separate pictures. Side by side, a draft that is a little smaller, larger or shifted against the drawing looks right, so a check round can accept a misplaced plan. The first runs against the real model (`claude-opus-5-5`, the napkin test image) were used to tune this.

**Decision:**
- In check rounds the draft is drawn in red over the photo, at the size the model was sent, instead of on white. The check prompt says red should cover each drawn line: a drawn line with no red on it, or red with no line under it, is an error. Position and size are checked before the parts. About one wall thickness of difference counts as in place, because hand-drawn lines wobble.
- Every round also gets the box around the photo's dark pixels (`ink_box`), measured by the program and given as the drawing's likely outer edge. No box is sent when the photo has too little contrast, or when the dark pixels reach every edge (a shadow or a table).
- The user still sees only the clean redraw. The overlay is only the model's input.

**Consequences:** On the test image the walls now land within 3 px of the ink, in three rounds (about 33k tokens in and 8k out, about 76 s). A dark border or shadow inside the photo can widen the box; the prompt names those cases so the model can set the box aside.

## D-030: Matched CAD rooms survive the redraw integration

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #108

**Context:** Main's new sketch redraw applies to image documents, including a PNG whose rooms now come from its native DXF companion. Generating another model-made set of rooms would mix approximate and exact geometry and could duplicate quantities.

**Decision:** A matched CAD PNG renders its clean sheet from the existing CAD elements immediately. Its upscale endpoint returns a no-op without model calls or element changes. Other raster sketches retain main's model redraw. Preserve the PNG image load/error timeout and retry behavior alongside the redraw UI; allow the synchronous sketch API request the server's default bounded claim budget rather than the normal 30-second document request budget.

**Consequences:** CAD-matched room geometry, identifiers and areas remain unchanged when switching views or requesting upscale. PNG-only sketches continue to use the model loop. Main and the earlier unmerged branches used some overlapping decision IDs; the existing entries are preserved and are distinguished by their titles and issue references.


## D-031: Claude omits unused tool filters to stay within strict-schema limits

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #111

**Context:** Claude rejected the complete request before answering because the shared strict tool schemas contained 15 nullable parameters and the answer schema contained five more. Anthropic limits union parameters across all strict schemas to 16.

**Decision:** Adapt only Claude's tool definitions: a required nullable filter becomes an optional property of its non-null type. Existing Pydantic handlers already default missing filters to None. Keep required inputs, enum constraints, strict validation, every tool and the structured answer. Deep-copy shared definitions so the Verda path is unchanged. Regression tests cover the actual request payload and the combined schema budget.

**Consequences:** The request has five union parameters and 15 optional tool parameters, within Claude's documented limits. No tools or filters are removed. Future schema additions must keep the combined tool/answer budget within provider limits.

## D-032: `make up-*` start in the background and smoke-check the stack

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #107 (part)

**Context:** `make up`, `up-aiven` and `up-local` ran `docker compose up --build` in the foreground, so nothing checked that the started stack was actually reachable. A stack could look up while :8080 returned 502 (nginx with a stale backend address, #64), no worker listened, or the UI build was broken, and people found out in the browser.

**Decision:**
- The `up-*` targets run `docker compose up --build --detach`, then `make smoke` with a 180 s budget. Logs are followed with `make logs`. No `--wait`: it would also block on vision's healthcheck, and the app works without vision (ingest falls back to pixel heuristics).
- `scripts/smoke.sh` checks from the host, retrying for up to `SMOKE_TIMEOUT` seconds (default 60): `/api/health` on :8000 reports `"ok":true` (it always answers 200, so the body is read), `ingest_workers` is above 0 (waited for too, because the worker registers with the queue a moment after it starts; a missing count fails), `/api/health` through :8080 also answers (nginx proxy), and :8080 serves the UI page. Each failure names the likely cause and the command to look further. `API_URL` and `WEB_URL` override the ports.
- `scripts/smoke-test.sh` tests it against local fake servers and runs in `make check` and CI.

**Consequences:** `make up-*` return to the prompt with a pass or a named failure instead of streaming logs. A broken proxy or a stopped frontend shows up as a failed proxy check (the #64 cause is fixed by D-033). The rest of #107 (`make dev`, `make doctor`, keyring helper, per-checkout project names) is still open.

## D-033: The UI's nginx finds the backend per request, at an address from `BACKEND_URL`

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #107 (part), fixes #64

**Context:** `frontend/nginx.conf` had `proxy_pass http://backend:8000;`. nginx resolves a literal host once at start-up, so it kept a recreated backend's old IP and :8080 returned 502 (#64), and it refused to start at all when no `backend` host existed. That blocks deploying the UI image on its own, which we are trying on Aiven Runtime (project `junction-stoa-winners`, app `askBob`, aws-eu-central-1); the Compose-to-Runtime route would also create extra Postgres and Valkey services from our offline-profile containers.

**Decision:**
- The config becomes `frontend/nginx.conf.template`, filled by the nginx image's entrypoint at start-up (only `BACKEND_URL` and `NGINX_LOCAL_RESOLVERS` are substituted).
- `proxy_pass` uses a variable built from `BACKEND_URL` (Dockerfile default `http://backend:8000`), with `resolver` set to the container's own DNS servers from `/etc/resolv.conf` (`NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1`), cached 10 s. Not Docker's `127.0.0.11`, which does not exist outside Docker networks.
- `BACKEND_URL` must be `http(s)://host[:port]`: with a variable, nginx would send a URL's path in place of every request path. `frontend/docker-entrypoint.d/16-check-proxy.envsh` drops a trailing slash and stops the container, saying why, on a path or when `/etc/resolv.conf` has no nameserver.
- nginx's resolver ignores `resolv.conf` search domains, so outside Compose the host must be a full name (`api.example.com`).
- The backend gets its own host name in `Host` (nginx's default) with SNI on and its certificate checked against the image's CA bundle, so an HTTPS backend behind a router works; the browser's host goes in `X-Forwarded-Host`, and `X-Forwarded-Proto` keeps an incoming one from a TLS-terminating router. The backend only reads the request path.
- `scripts/frontend-image-test.sh` (CI containers job, `make frontend-image-check`) checks the image starts without a backend, proxies to `BACKEND_URL` (also with a trailing slash), follows a backend recreated on a new IP, and refuses a path or a missing nameserver.

**Consequences:** Recreating the backend no longer needs a frontend restart (verified on the local stack with the backend moved to a new IP, plus SSE on `/api/events`). The UI image can be deployed alone; until a backend is hosted, its `/api` calls return 502. Hosting the API, worker and vision on Runtime is not decided here: the shared `/data` volume and vision's 6 GB need checking first.

## D-034: The demo runs on Aiven Runtime as one container: UI, API and worker

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #116

**Context:** We want the app hosted for the Junction demo on Aiven Runtime, next to our Aiven Postgres and Valkey. Runtime apps cannot share a disk and "an Aiven Runtime application cannot be integrated with another Runtime application"; ports are public HTTPS only. Our API and worker share `/data` for uploads, page images, IFC and meshes (`backend/app/storage.py`), so separate apps would need that storage moved first (into Postgres or an object store), which is more than the event leaves time for.

**Decision:**
- The root `Dockerfile` (at the root because Runtime's manifest scan uses each Dockerfile's own folder as build context; a root `.dockerignore` keeps the context to `backend/`, `frontend/` and `deploy/`, without `.env` files), with `deploy/runtime/nginx.conf` and `start.sh`, runs nginx, uvicorn and the RQ worker in one container as the unprivileged `app` user. nginx listens on 8080 and proxies `/api` to `127.0.0.1:8000`.
- `deploy/runtime/start.sh` starts the API, waits for it to answer (it creates the schema) before starting the worker, then nginx. If any process exits, it stops the others and exits, so Runtime restarts the container whole. On SIGTERM it stops the API and worker with TERM and nginx with QUIT (graceful), waits up to `STOP_GRACE_S` (20 s) and then kills what is left, so a worker busy with a minutes-long job does not hold a redeploy; that job is cut off and requeued by the next worker (whose file is gone after a redeploy anyway).
- It deploys as the existing Runtime app `askBob` (aws-eu-central-1, port 8080, at least `startup-50-2560`). Secrets (`DATABASE_URL`, `VALKEY_URL`, `ANTHROPIC_API_KEY`) are set on that app in the console.
- `scripts/runtime-image-test.sh` (CI containers job, `make runtime-image-check`) builds the image, runs it against throwaway Postgres and Valkey and checks `scripts/smoke.sh` through the single port, SSE, a non-root user, that a stop finishes within the grace period even with a stuck worker, and that the container stops when the worker dies.

**Consequences:** One app to configure and one address. Files are on the container's own disk: a redeploy or restart loses them while their Postgres rows stay, so documents uploaded before a redeploy break and have to be uploaded again. No vision service runs (raster ingest uses pixel heuristics, D-023). Verified locally: a CubiCasa PNG ingested in about 21 s with 70 elements; idle memory is about 300 MB. Not yet verified on Runtime itself, including its request timeout for the minutes-long sketch redraw, its upload size limit, and whether it runs the container as the image's `app` user (UID 1000, which owns `/data`); a forced other UID could not write `/data`. The lasting setup (files in Postgres or an object store, separate API and vision apps) is a later issue. The `frontend/` image and `BACKEND_URL` (D-033) stay for Compose and for that later split.

## D-035: One Export menu holds Download IFC, Download SVG and Print

**Date:** 2026-11-14 · **Status:** Accepted · **Issue:** #109 · **Supersedes in part:** D-024 (Download IFC above the plan), D-028 (Download SVG and Print in the plan toolbar)

**Context:** Files left the app from three places: Download IFC at the bottom of the documents panel, a second Download IFC above the plan while the panel was collapsed, and Download SVG and Print in the plan toolbar, laid out invisibly on the original view so the toolbar would not shift. The copy above the plan took a whole row for one button and was easy to miss. The Redraw card, once open, could only be left through the Original tab.

**Decision:**
- **One Export ▾ menu** with Download IFC, Download SVG and Print. It sits where Download IFC was, at the bottom of the documents panel, and opens upward. Hiding the panel hides it too: nothing moves to the app bar, which keeps only the panel toggle, the theme and Upload.
- Download IFC is greyed out when the document has no IFC. Download SVG and Print are greyed out until the redrawn sheet is on screen; the plan viewer hands the menu those two actions while it is.
- The plan toolbar keeps page navigation, Original / Redrawn and the layers; the row above the plan shows only when there are Plan / 3D model tabs.
- The menu and the Redraw card close on a click anywhere outside them or on Esc (`useDismiss`). Closing the card during a redraw only hides it: the server finishes, and Redrawn shows the result.

**Consequences:** Export has one place, and the plan toolbar no longer reserves space for hidden buttons. With the documents panel hidden there is no way to export until it is shown again. The 3D tab can still download the IFC from the menu; SVG and Print stay greyed out there.

## D-036: Every question reports what it used; the eval turns that into cost

**Date:** 2026-11-14 · **Status:** Accepted · **Refines:** D-019

**Context:** Low inference cost is a quarter of the judging, and we could not say what an answer costs. `/api/ask` counted input and output tokens, but only for answered questions, only into `qa_log`, and with cached input counted differently per provider. The eval printed accuracy and nothing about cost (#98).

**Decision:**
- **Usage is counted per question in one shape** (`app/domain/usage.py`): input tokens that were not cached, input read from the provider's prompt cache, input written to it, output tokens, and the number of model requests. It lives on the tool context, so a question that fails still reports what it used.
- **The closing `done` event of `/api/ask` carries it**, with the model, the number of tool calls, the time and whether the answer came from the answer cache. The browser ignores the event's data today.
- **`qa_log.input_tokens` now counts every input token**, cached or not. Before, the Claude loop left cached input out.
- **The eval prices it** (`eval/prices.py`, dollars per million tokens). Anthropic's list prices are in the table. Verda shows its prices only in the Console, so they are passed with `--price MODEL=IN,OUT` or added to the table; a model without a price reports "price unknown", never a guess. So does a question where Claude's refusal fallback (`fallbacks="default"`) re-ran a request on another model: the `done` event counts those as `fallback_requests`, and their tokens are billed at a price we don't know.
- **`run_eval` prints** tokens, tool calls, seconds and cost per question, averages per source and type, and errors by code. Answers served from the answer cache made no model call and are left out of the averages. `--out` writes one line per question, so two runs can be compared.

**Consequences:** A run now gives accuracy and cost side by side: on DeepSeek, eight questions about four preview drawings averaged 62,000 input tokens and 10 tool calls each. Prices are a hand-kept table and go stale when a provider changes them. No schema change: steps and cached tokens are in the event and the eval file, not in `qa_log`.
