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
| D-018 | 2026-11-14 | The plan is a pan/zoom canvas; nothing that appears moves it | Accepted |
| D-019 | 2026-11-14 | Answers carry a numeric value; the eval scores it by question type | Accepted |
| D-020 | 2026-11-14 | The Q&A agent can run on Kimi K3.1 Pro on Verda (`LLM_PROVIDER`) | Accepted |
| D-021 | 2026-11-14 | A citation's box is the element's extent; the printed name is the fallback | Accepted |
| D-022 | 2026-11-14 | A floor-plan model (CubiCasa5k) in its own `vision` service reads raster plans | Accepted |
| D-023 | 2026-11-14 | The `vision` service works within a fixed pixel budget, whatever the upload | Accepted |
| D-028 | 2026-11-14 | IFC base quantities are stored in SI units and totalled by the server | Accepted |

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

**Date:** 2026-11-14 · **Status:** Accepted · **Refines:** D-016

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

## D-028: IFC base quantities are stored in SI units and totalled by the server

**Date:** 2026-11-14 · **Status:** Accepted · **Refines:** D-006, D-015

**Context:** The dataset asks for totals over an IFC model: the net volume of all walls or slabs on a storey, the net side area and the length of all walls, the net floor area of all rooms (#96). The agent could only list elements (50 at most), open each one for its property sets and add the numbers itself, in the model's own units: the Molio model gives wall lengths in millimetres and volumes in m³.

**Decision:**
- **Ingest keeps each IFC element's base quantities in SI units** under `properties.quantities`: lengths in m, areas in m², volumes in m³, converted with the model's unit scales. They come only from the standard sets (`Qto_*` in IFC4, `BaseQuantities` in IFC2X3). Authoring tools' own sets, such as `ArchiCADQuantities`, are left out, because they reuse names like "Area" with other meanings. Weights and counts are left out too.
- **A `sum_quantity` agent tool adds them up**: one quantity over the elements of one kind, optionally on one storey. It returns the total with its unit, how many elements were summed, how many of the selected elements lacked the quantity, totals per storey, and the elements summed (50 listed) to cite and highlight. The summing rule is a pure function (`app/domain/quantities.py`).
- **A storey with no elements of that kind is an error that lists the storeys that have them**, so a misspelt storey is not read as a total of 0.
- The prompt sends every such total to the tool, and asks for a caveat when elements lacked the quantity.

**Consequences:**
- Checked without the model against the dataset's answers: all 35 totals for the Molio model match within 2% (most to three decimals).
- IFC models ingested before this change have no `quantities` until they are processed again.
- The Esplanades model has no quantity sets on its rooms, so its four room-area totals report every room as lacking the quantity. Areas from geometry are #37.
- An element nested inside another of the same kind is summed like any other. If a model gives quantities to both a parent and its parts, the total counts them twice; we have not seen such a model.
