"""Check that an answer only cites evidence the agent actually looked at.

The agent's tools record every element they return and every page region they
show. A citation counts as verified only when it points at that evidence, so the
UI can tell a grounded answer from a guess.
"""

from dataclasses import dataclass

from app.domain.geometry import BBox, bbox_iou


@dataclass(frozen=True)
class EvidenceItem:
    element_id: str | None
    document_id: str
    page_id: str | None
    page_index: int | None
    bbox: BBox | None
    ifc_guid: str | None


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
    """What the browser needs to highlight a citation: document, page, box, 3D id.

    Verified citations take their location from the evidence (not from the model).
    """
    c, ev = checked.citation, checked.evidence
    use_evidence = ev is not None and c.element_id is not None
    bbox = ev.bbox if use_evidence and ev else c.bbox
    return {
        "element_id": c.element_id,
        "document_id": ev.document_id if ev else None,
        "page_id": ev.page_id if ev else c.page_id,
        "page_index": ev.page_index if ev else None,
        "bbox": list(bbox) if bbox else None,
        "ifc_guid": ev.ifc_guid if ev else None,
        "note": c.note,
        "verified": checked.verified,
    }


def _check(
    c: Citation, elements: dict[str, EvidenceItem], regions: list[EvidenceItem]
) -> CheckedCitation:
    if c.element_id and c.element_id in elements:
        return CheckedCitation(c, True, elements[c.element_id])
    if c.page_id and c.bbox:
        for region in regions:
            if region.page_id == c.page_id and region.bbox and _same_area(region.bbox, c.bbox):
                return CheckedCitation(c, True, region)
    return CheckedCitation(c, False, None)


def _same_area(seen: BBox, cited: BBox) -> bool:
    inside = (
        seen[0] <= cited[0] and seen[1] <= cited[1] and cited[2] <= seen[2] and cited[3] <= seen[3]
    )
    return inside or bbox_iou(seen, cited) >= REGION_MATCH_IOU
