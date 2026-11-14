# The building model

Every upload, whatever its format, ends up in the same shape: an **IFC4 model**, plus an index of its elements in Postgres. The UI and the agent only ever see that shape. What differs between formats is how much of it we can fill, and how sure we are, which each element records in `source` and `confidence`.

## One pipeline

```
IFC upload ─────────────────────────────┐
DXF ──▶ dxf_reader ──┐                  │
DWG ──▶ dwg2dxf ─────┤                  │
PDF ──▶ pdf_reader ──┼──▶ ifc_writer ──▶ IFC ──▶ ifc_index ──▶ elements (Postgres)
SVG ──▶ pdf_reader ──┤                  │      └─▶ ifc_mesh ──▶ mesh.json (3D viewer)
PNG/JPG/TIFF ──▶ image_reader ──┘       │
                                        └─▶ download (any IFC tool)
```

The code is in `backend/app/ingest/pipeline.py` (`build`), which has no database access and is tested end to end for every format in `pipeline_test.py`. The worker job (`jobs.py`) only stores what `build` returns.

## Element fields

| Field | Meaning |
|---|---|
| `kind` | `room`, `wall`, `door`, `window`, `fixture`, `unit` (apartment), `storey`, `stair`, `slab`, `column`, `beam`, `roof`, `railing`, `text`, `dimension`, `scale`, `area`, `room_number`, `element` (anything else) |
| `text`, `label`, `name` | As printed (`"Zimmer"`), normalised (`"2.01"`, `"09"`), and human-readable (`"room (Zimmer) 2.01"`) |
| `value_mm` | The one number that matters for the kind: door or window width, dimension value, storey elevation |
| `properties` | Everything else, e.g. `number`, `unit`, `area_m2`, `outdoor`, `shaft`, `subtype` (`wc`, `washbasin`, `shower`, `bathtub`, `sink`), `storey`, `part_of`, `host`, `ifc_class`, `type_name`, IFC property sets |
| `ifc_guid` | The element's IFC GlobalId: the same id in the IFC file, the 3D mesh and citations |
| `page` + `bbox` | Where it is on a drawing page (pixels of the rendered page); empty for IFC uploads |
| `source` | `ifc`, `dxf`, `pdf_text`, `pdf_vector`, `ocr`, `derived` |
| `confidence` | 1.0 when read exactly (IFC, DXF, PDF text); lower when inferred (OCR, computer vision) |

## How kinds map to IFC

Defined once, in both directions, in `backend/app/domain/model_rules.py`:

| Kind | IFC |
|---|---|
| room | `IfcSpace` with `Qto_SpaceBaseQuantities.NetFloorArea` |
| unit (apartment) | `IfcZone` grouping its spaces |
| wall, door, window, stair, slab, column | `IfcWall`, `IfcDoor`, `IfcWindow`, `IfcStair`, `IfcSlab`, `IfcColumn` |
| fixture with a known subtype | `IfcSanitaryTerminal` with `PredefinedType` `TOILETPAN`, `WASHHANDBASIN`, `SHOWER`, `BATH` or `SINK` |
| other fixtures and kinds | `IfcBuildingElementProxy`, `ObjectType = "bob:<kind>"` |
| text, dimension, scale, area, room number | `IfcAnnotation`, `ObjectType = "bob:<kind>"` |

Each object written from a drawing carries a `Bob_Element` property set (kind, source, confidence, page, box, all properties as JSON), so reading the IFC back loses nothing.

## Counting rules (in `ifc_index.py`)

- An object nested in another object of the same kind is a part (`properties.part_of`), not another element. Stair risers are the case seen in the dataset: 579 `IfcStair` objects make 15 stairs.
- IFC2X3 has no `IfcSanitaryTerminal`: an `IfcFlowTerminal` typed by `IfcSanitaryTerminalType` is a fixture.
- Areas from quantity sets are converted with the file's area unit; lengths with its length unit.

## 3D geometry for drawings

A drawing gives footprints, not heights. Shapes are extruded with fixed, documented heights (`model_rules.py`): walls and rooms 2600 mm, windows from 900 to 2100 mm, fixtures 450 mm. Doors become a 20 mm floor marker, because a plan shows where a door is, not where its leaf stands. Uploaded IFC models keep their real geometry.

## Large models and failures

- Meshes are stored gzipped. Models over 1.5 million triangles are trimmed for the browser, keeping building fabric first, then fixtures, then pipes and furniture (`domain/mesh_budget.py`). Trimmed parts stay in the data and still count in answers.
- A reader that knows why it failed raises `ReaderError` with a code. The API turns the code into a message for the user (`domain/ingest_errors.py`): damaged file, password-protected PDF, no DWG converter, empty drawing.
- A model that cannot be meshed, or a drawing whose IFC cannot be written, still keeps its elements; the document records a warning.

