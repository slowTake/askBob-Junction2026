"""Plan tools against a small page: a measured line, an area label, a route to an exit."""

import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Document, Element, Page
from app.qa.context import ToolContext, ToolInputError
from app.qa.plan_tools import run_plan_tool


@pytest.fixture
def plan() -> Iterator[tuple[ToolContext, dict[str, Element]]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(engine, expire_on_commit=False)()
    doc = Document(filename="plan.png", kind="image", sha256="0" * 64, size_bytes=1)
    page = Page(document=doc, index=0, width_px=200, height_px=100, mm_per_px=10.0)
    db.add_all([doc, page])
    db.flush()

    def el(kind: str, bbox: list[float], **props: Any) -> Element:
        e = Element(document_id=doc.id, page_id=page.id, kind=kind, bbox=bbox,
                    properties=props, source="ocr", text=kind)  # fmt: skip
        db.add(e)
        return e

    # Two rooms split by a wall at x 98..102 with a door at y 40..60.
    els = {
        "left": el("room", [0, 0, 98, 100]),
        "right": el("room", [102, 0, 200, 100]),
        "wall": el("wall", [98, 0, 102, 100]),
        "door": el("door", [96, 40, 104, 60]),
        "kitchen": el("room", [10, 10, 40, 40]),
        "bath": el("room", [50, 10, 80, 40]),
    }
    db.commit()
    yield ToolContext(db=db, scope=[doc.id]), els
    db.close()


def _run(ctx: ToolContext, name: str, **args: Any) -> dict[str, Any]:
    return json.loads(run_plan_tool(name, args, ctx))


def test_measure_draws_only_the_line(plan: tuple[ToolContext, dict[str, Element]]) -> None:
    ctx, els = plan
    _run(ctx, "measure_between", element_a=str(els["kitchen"].id), element_b=str(els["bath"].id))
    [view] = ctx.views
    assert view["element_ids"] == []  # nothing lit up: the line says it all
    assert view["line"]["label"] == "0.40 m"  # centres 25 and 65 px apart x 10 mm/px, by hand
    assert set(ctx.elements) == {str(els["kitchen"].id), str(els["bath"].id)}  # still citable


def test_highlight_with_a_label_writes_it_over_the_elements(
    plan: tuple[ToolContext, dict[str, Element]],
) -> None:
    ctx, els = plan
    ids = [str(els["kitchen"].id), str(els["bath"].id)]
    _run(ctx, "highlight", element_ids=ids, caption=None, label="Apartment A · 18 m²")
    [view] = ctx.views
    # Union box 10..80 x 10..40: its centre is (45, 25), by hand.
    assert view["labels"] == [{"at": [45.0, 25.0], "text": "Apartment A · 18 m²"}]
    assert view["path"] is None


def test_highlight_without_a_label_has_none(plan: tuple[ToolContext, dict[str, Element]]) -> None:
    ctx, els = plan
    _run(ctx, "highlight", element_ids=[str(els["kitchen"].id)], caption=None, label=None)
    assert ctx.views[0]["labels"] == []


def test_route_goes_through_the_door_and_reports_its_length(
    plan: tuple[ToolContext, dict[str, Element]],
) -> None:
    ctx, els = plan
    out = _run(ctx, "route", from_element=str(els["left"].id), to_element=str(els["right"].id))
    [view] = ctx.views
    points = view["path"]["points"]
    assert points[0] == pytest.approx([49, 50], abs=2) and points[-1] == pytest.approx(
        [151, 50], abs=2
    )
    # Room centres (49, 50) and (151, 50) face each other through the door: a straight
    # 102 px walk, x 10 mm/px = 1.02 m (by hand).
    assert out["length_mm"] == pytest.approx(1020, abs=40)
    assert view["path"]["label"] == f"{out['length_mm'] / 1000:.1f} m"
    assert view["element_ids"] == []


def test_route_with_no_way_through_is_an_input_error(
    plan: tuple[ToolContext, dict[str, Element]],
) -> None:
    ctx, els = plan
    ctx.db.delete(els["door"])
    ctx.db.commit()
    with pytest.raises(ToolInputError):
        _run(ctx, "route", from_element=str(els["left"].id), to_element=str(els["right"].id))


def test_route_rejects_elements_outside_the_scope(
    plan: tuple[ToolContext, dict[str, Element]],
) -> None:
    ctx, els = plan
    with pytest.raises(ToolInputError):
        _run(ctx, "route", from_element=str(uuid.uuid4()), to_element=str(els["right"].id))
