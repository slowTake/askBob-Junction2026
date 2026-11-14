"""Check that an answer only cites evidence the agent actually looked at.

The agent's tools record every element they return and every page region they
show. A citation counts as verified only when it points at that evidence, so the
UI can tell a grounded answer from a guess.
"""

from dataclasses import dataclass
from typing import Literal

from app.domain.extent import Target as ExtentTarget
from app.domain.extent import element_extent
from app.domain.geometry import BBox, Point, bbox_iou

EvidenceTarget = ExtentTarget | Literal["region"]


@dataclass(frozen=True)
class EvidenceItem:
    element_id: str | None
    document_id: str
    page_id: str | None
    page_index: int | None
    bbox: BBox | None  # for elements: the element's extent (see domain/extent.py)
    ifc_guid: str | None
    target: EvidenceTarget  # what bbox shows: the element, only its label, or a viewed region
    polygon: tuple[Point, ...] | None = None
    label_bbox: BBox | None = None


def element_evidence(
    element_id: str,
    document_id: str,
    page_id: str | None,
    page_index: int | None,
    kind: str,
    bbox: BBox | None,
    properties: dict[str, object],
    ifc_guid: str | None,
) -> EvidenceItem:
    """Evidence for an element a tool returned or showed, located by its extent.

    Every tool records elements through this, so a citation shows the same shape
    whichever tool the agent used. `label_bbox` is set only when the extent is an
    outline and the stored box is the printed name inside it.
    """
    extent = element_extent(kind, bbox, properties)
    label = bbox if extent.polygon is not None and extent.bbox != bbox else None
    return EvidenceItem(
        element_id, document_id, page_id, page_index, extent.bbox, ifc_guid,
        extent.target, extent.polygon, label,
    )  # fmt: skip


@dataclass(frozen=True)
class Citation:
    element_id: str | None
    page_id: str | None
    bbox: BBox | None
    note: str


@dataclass(frozen=True)
class CheckedCitation:
    citation: Citation
    verified: bool
    evidence: EvidenceItem | None


REGION_MATCH_IOU = 0.3


def check_citations(
    citations: list[Citation],
    elements: dict[str, EvidenceItem],
    regions: list[EvidenceItem],
) -> tuple[list[CheckedCitation], bool]:
    """Return each citation with its matching evidence, and whether all are verified.

    An answer without citations is never verified.
    """
    checked = [_check(c, elements, regions) for c in citations]
    all_verified = bool(checked) and all(c.verified for c in checked)
    return checked, all_verified


def citation_payload(checked: CheckedCitation) -> dict[str, object]:
    """What the browser needs to highlight a citation: document, page, shape, 3D id.

    Element citations take their location from the evidence (not from the model):
    the element's outline when known, else its label (`target` says which). Region
    citations keep the cited box, which lies within what the agent viewed.
    """
    c, ev = checked.citation, checked.evidence
    is_element = ev is not None and ev.element_id is not None
    bbox = ev.bbox if ev is not None and is_element else c.bbox
    target = ev.target if ev is not None else None
    return {
        "element_id": c.element_id,
        "document_id": ev.document_id if ev else None,
        "page_id": ev.page_id if ev else c.page_id,
        "page_index": ev.page_index if ev else None,
        "bbox": list(bbox) if bbox else None,
        "ifc_guid": ev.ifc_guid if ev else None,
        "polygon": [list(p) for p in ev.polygon] if ev and ev.polygon else None,
        "label_bbox": list(ev.label_bbox) if ev and ev.label_bbox else None,
        "target": target,
        "note": c.note,
        "verified": checked.verified,
    }


def _check(
    c: Citation, elements: dict[str, EvidenceItem], regions: list[EvidenceItem]
) -> CheckedCitation:
    if c.element_id:
        # An element id must be one a tool returned; a viewed region never rescues it.
        found = elements.get(c.element_id)
        return CheckedCitation(c, found is not None, found)
    if c.page_id and c.bbox and _is_box(c.bbox):
        for region in regions:
            if region.page_id == c.page_id and region.bbox and _same_area(region.bbox, c.bbox):
                return CheckedCitation(c, True, region)
    return CheckedCitation(c, False, None)


def _is_box(b: BBox) -> bool:
    return b[2] > b[0] and b[3] > b[1]


def _same_area(seen: BBox, cited: BBox) -> bool:
    inside = (
        seen[0] <= cited[0] and seen[1] <= cited[1] and cited[2] <= seen[2] and cited[3] <= seen[3]
    )
    return inside or bbox_iou(seen, cited) >= REGION_MATCH_IOU
