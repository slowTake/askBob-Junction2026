"""One pipeline for every format: read -> IFC -> index -> mesh. No database here.

    IFC upload:         the file itself is the model
    DXF/DWG/PDF/SVG/PNG: reader -> elements -> IFC (ifc_writer)
    then, for all:      IFC -> elements (ifc_index), IFC -> mesh (ifc_mesh)

Because every format is indexed by the same IFC reader, the app and the agent see
one shape whatever was uploaded; only `source` and `confidence` differ.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.bim.ifc_index import index_ifc
from app.bim.ifc_mesh import ifc_to_mesh
from app.bim.ifc_plans import floor_plans
from app.bim.ifc_writer import write_model
from app.config import Settings
from app.ingest.errors import ReaderError
from app.ingest.registry import READERS
from app.ingest.types import ExtractedElement, ExtractedPage, Progress

log = logging.getLogger(__name__)


@dataclass
class BuiltDocument:
    pages: list[ExtractedPage]
    elements: list[ExtractedElement]
    model_path: Path | None  # the IFC: the original for IFC uploads, generated otherwise
    mesh: dict[str, Any] | None
    meta: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def build(
    path: Path, kind: str, settings: Settings, model_out: Path, progress: Progress
) -> BuiltDocument:
    """Read any supported file into pages, indexed elements, an IFC model and a mesh."""
    warnings: list[str] = []
    pages: list[ExtractedPage] = []
    meta: dict[str, Any] = {}
    model_path: Path | None = path

    if kind != "ifc":
        reader = READERS.get(kind)
        if reader is None:
            raise ReaderError("unreadable_file", f"no reader for {kind}")
        extracted = reader(path, settings, lambda stage, f: progress(stage, 0.6 * f))
        pages, meta = extracted.pages, extracted.meta
        found = [_on_page(el, page.index) for page in pages for el in page.elements]
        found += extracted.elements
        if not pages and not found:
            raise ReaderError("empty_drawing")
        progress("modelling", 0.65)
        try:
            write_model(found, model_out, project_name=path.stem)
            model_path = model_out
        except Exception:  # keep what we read even if IFC writing fails
            log.exception("writing IFC failed for %s", path.name)
            warnings.append("ifc_write_failed")
            return BuiltDocument(pages, found, None, None, meta, warnings)

    progress("indexing", 0.75)
    assert model_path is not None
    elements, model_meta = index_ifc(model_path)
    meta = {**meta, "model": model_meta}

    mesh: dict[str, Any] | None = None
    if kind == "ifc":  # 3D only for real models; a floor plan's 3D would be invented (D-016)
        progress("meshing", 0.85)
        try:
            mesh = ifc_to_mesh(model_path)
            if not mesh["meshes"]:
                mesh = None
        except Exception:  # a model we can't triangulate still answers questions
            log.exception("meshing failed for %s", path.name)
            warnings.append("mesh_failed")
        if mesh is not None:
            progress("drawing plans", 0.9)
            pages = _plans(mesh, elements, model_meta.get("storeys", []), warnings)
    return BuiltDocument(pages, elements, model_path, mesh, meta, warnings)


def _plans(
    mesh: dict[str, Any], elements: list[ExtractedElement], storeys: list[Any], warnings: list[str]
) -> list[ExtractedPage]:
    """One floor plan page per storey; drawn elements get their page and box."""
    try:
        pages, placed = floor_plans(mesh, elements, storeys)
    except Exception:  # plans are a view; the model stays usable without them
        log.exception("drawing floor plans failed")
        warnings.append("plans_failed")
        return []
    for el in elements:
        spot = placed.get(el.ifc_guid or "")
        if spot is not None:
            el.page_index, el.bbox = spot.page_index, spot.bbox
            if el.kind == "room":
                el.properties["polygon_px"] = [
                    [round(x, 1), round(y, 1)] for x, y in spot.polygon_px
                ]
    return pages


def _on_page(el: ExtractedElement, index: int) -> ExtractedElement:
    el.page_index = index
    return el
