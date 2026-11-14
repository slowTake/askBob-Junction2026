from app.domain.citations import Citation, EvidenceItem, check_citations, citation_payload

ROOM = EvidenceItem("el-1", "doc-1", "page-1", 0, (10, 10, 30, 20), None)
REGION = EvidenceItem(None, "doc-1", "page-1", 0, (0, 0, 100, 100), None)


def test_element_citation_is_verified() -> None:
    checked, ok = check_citations([Citation("el-1", None, None, "room label")], {"el-1": ROOM}, [])
    assert ok
    assert checked[0].evidence == ROOM


def test_unknown_element_is_not_verified() -> None:
    _, ok = check_citations([Citation("el-404", None, None, "made up")], {"el-1": ROOM}, [])
    assert not ok


def test_region_inside_viewed_region_is_verified() -> None:
    cite = Citation(None, "page-1", (20, 20, 40, 40), "door swing")
    _, ok = check_citations([cite], {}, [REGION])
    assert ok


def test_region_on_other_page_is_not_verified() -> None:
    cite = Citation(None, "page-2", (20, 20, 40, 40), "door swing")
    _, ok = check_citations([cite], {}, [REGION])
    assert not ok


def test_no_citations_means_not_verified() -> None:
    _, ok = check_citations([], {"el-1": ROOM}, [])
    assert not ok


def test_payload_for_element_uses_evidence_location() -> None:
    checked, _ = check_citations([Citation("el-1", None, (0, 0, 1, 1), "x")], {"el-1": ROOM}, [])
    payload = citation_payload(checked[0])
    assert payload["bbox"] == [10, 10, 30, 20]  # from the evidence, not the model's (0, 0, 1, 1)
    assert payload["page_index"] == 0
    assert payload["verified"] is True


def test_payload_for_region_keeps_cited_box() -> None:
    cite = Citation(None, "page-1", (20, 20, 40, 40), "door swing")
    checked, _ = check_citations([cite], {}, [REGION])
    payload = citation_payload(checked[0])
    assert payload["bbox"] == [20, 20, 40, 40]
    assert payload["document_id"] == "doc-1"


def test_payload_for_unverified_citation() -> None:
    checked, _ = check_citations([Citation("el-x", "page-9", None, "guess")], {}, [])
    payload = citation_payload(checked[0])
    assert payload["verified"] is False
    assert payload["page_id"] == "page-9"
    assert payload["document_id"] is None


def test_one_bad_citation_fails_the_answer() -> None:
    cites = [Citation("el-1", None, None, "ok"), Citation("el-x", None, None, "bad")]
    checked, ok = check_citations(cites, {"el-1": ROOM}, [])
    assert not ok
    assert [c.verified for c in checked] == [True, False]


def test_made_up_element_id_is_not_rescued_by_a_viewed_region() -> None:
    # D-006: a citation must point at something a tool returned. "el-404" was never
    # returned, so the citation fails even though its box lies inside a viewed region (#11).
    cite = Citation("el-404", "page-1", (20, 20, 40, 40), "made up")
    checked, ok = check_citations([cite], {"el-1": ROOM}, [REGION])
    assert not ok
    payload = citation_payload(checked[0])
    assert payload["verified"] is False
    assert payload["bbox"] == [20, 20, 40, 40]  # the cited box, not the whole viewed region


def test_inverted_box_is_not_a_region() -> None:
    # x1 < x0 and y1 < y0: not a rectangle, so it cannot lie "inside" what was viewed.
    cite = Citation(None, "page-1", (40, 40, 20, 20), "inverted")
    _, ok = check_citations([cite], {}, [REGION])
    assert not ok


def test_empty_box_is_not_a_region() -> None:
    # Zero width (x0 == x1): nothing to look at.
    cite = Citation(None, "page-1", (20, 20, 20, 40), "empty")
    _, ok = check_citations([cite], {}, [REGION])
    assert not ok
