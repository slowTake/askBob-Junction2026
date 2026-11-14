"""Recognised questions are answered from the server's tools; the rest go to the agent (#97)."""

import json
import uuid
from typing import Any

import pytest

from app.config import Settings
from app.domain.intents import RoomRef
from app.models import Element
from app.qa import fast_path
from app.qa.fast_path import fast_events, room_ref
from app.qa.tools import ToolContext, ToolInputError

DOC = [{"id": "d1", "filename": "plan.ifc", "kind": "ifc", "page_count": 1}]
EMPTY: dict[str, Any] = {
    "intent": "other", "kind": None, "quantity": None, "subtype": None, "category": None,
    "name": None, "number": None, "unit": None, "storey": None, "refers_to_view": False,
}  # fmt: skip


def _settings(fast: str = "all") -> Settings:
    return Settings(database_url="postgresql://unused", valkey_url="redis://unused",
                    fast_path=fast)  # type: ignore[arg-type]  # fmt: skip


def _door(n: int, confidence: float = 1.0, page: bool = True) -> dict[str, Any]:
    door = {"id": f"e{n}", "kind": "door", "label": f"D{n}", "confidence": confidence}
    return {**door, "page_id": "p1"} if page else door


class Fakes:
    """What the router says and what the tools return, and every tool call made."""

    def __init__(self) -> None:
        self.intent: dict[str, Any] | None = {**EMPTY, "intent": "count", "kind": "door"}
        self.results: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.rooms: list[RoomRef] = []

    def run_tool(self, name: str, args: dict[str, Any], ctx: ToolContext) -> str:
        self.calls.append((name, args))
        if name == "highlight":
            ctx.views.append({"page_index": 0, "element_ids": args["element_ids"]})
            return json.dumps({"highlighted": len(args["element_ids"])})
        result = self.results[name]
        if isinstance(result, Exception):
            raise result
        return json.dumps(result)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    f = Fakes()
    monkeypatch.setattr(fast_path, "route", lambda question, settings, usage: f.intent)
    monkeypatch.setattr(fast_path, "run_tool", f.run_tool)
    monkeypatch.setattr(fast_path, "rooms", lambda ctx: f.rooms)
    return f


def _run(
    fast: str = "all",
    selected: list[str] | None = None,
    documents: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    ctx = ToolContext(db=None, scope=[])  # type: ignore[arg-type]  # the tools are faked
    return fast_events("How many doors?", documents or DOC, ctx, _settings(fast), selected)


def test_a_count_is_answered_cited_and_shown(fakes: Fakes) -> None:
    fakes.results["count_elements"] = {"total": 3, "elements": [_door(1), _door(2), _door(3)]}
    events = _run()
    assert events is not None
    assert [e["type"] for e in events] == ["step", "step", "view", "final"]
    assert [e["tool"] for e in events[:2]] == ["count_elements", "highlight"]
    answer = events[-1]["answer"]
    assert (answer.answer, answer.value, answer.unit) == ("3 doors.", 3.0, "count")
    assert [c.element_id for c in answer.citations] == ["e1", "e2", "e3"]
    assert (answer.confidence, answer.caveats) == ("high", "")
    assert fakes.calls[1] == ("highlight", {"element_ids": ["e1", "e2", "e3"],
                                            "caption": "3 doors.", "label": None})  # fmt: skip


def test_elements_without_a_plan_page_are_cited_but_not_highlighted(fakes: Fakes) -> None:
    fakes.results["count_elements"] = {"total": 1, "elements": [_door(1, page=False)]}
    events = _run()
    assert events is not None and [e["type"] for e in events] == ["step", "final"]


def test_detected_elements_answer_with_a_caveat_or_not_at_all(fakes: Fakes) -> None:
    # A door the floor-plan model found has confidence 0.7 (D-022).
    fakes.results["count_elements"] = {"total": 2, "elements": [_door(1), _door(2, 0.7)]}
    events = _run("all")
    assert events is not None
    assert events[-1]["answer"].confidence == "medium"
    assert "not checked" in events[-1]["answer"].caveats
    assert _run("exact") is None


def test_a_count_of_zero_goes_to_the_agent(fakes: Fakes) -> None:
    fakes.results["count_elements"] = {"total": 0, "elements": []}
    assert _run() is None


def test_a_quantity_total_over_part_of_the_elements_goes_to_the_agent(fakes: Fakes) -> None:
    fakes.intent = {**EMPTY, "intent": "quantity_total", "kind": "wall", "quantity": "NetVolume"}
    wall = {"id": "w1", "kind": "wall", "confidence": 1.0}
    fakes.results["sum_quantity"] = {
        "total": 7.75, "elements_summed": 3, "elements_without_quantity": 1, "elements": [wall],
    }  # fmt: skip
    assert _run() is None
    fakes.results["sum_quantity"]["elements_without_quantity"] = 0
    events = _run()
    assert events is not None
    assert (events[-1]["answer"].value, events[-1]["answer"].unit) == (7.75, "m3")


def test_an_apartment_total_lists_its_rooms(fakes: Fakes) -> None:
    fakes.intent = {**EMPTY, "intent": "area_total", "unit": "A"}
    rooms = [{"id": f"r{i}", "kind": "room", "name": f"room {i}", "confidence": 1.0}
             for i in range(2)]  # fmt: skip
    fakes.results["sum_room_areas"] = {"total_m2": 65.1, "rooms_counted": 2, "rooms": rooms}
    events = _run()
    assert events is not None
    assert events[-1]["answer"].answer == "65.1 m² for apartment A (2 rooms)."
    assert [c.note for c in events[-1]["answer"].citations] == ["room 0", "room 1"]


def test_one_room_is_looked_up_and_read(fakes: Fakes) -> None:
    fakes.intent = {**EMPTY, "intent": "room_area", "number": "1.13"}
    fakes.rooms = [RoomRef("r1", ("Bad",), "1.13", None, "A", 4.36),
                   RoomRef("r2", ("Bad",), "2.07", None, "B", 4.4)]  # fmt: skip
    fakes.results["get_element"] = {"id": "r1", "kind": "room", "name": "Bad", "confidence": 1.0}
    events = _run()
    assert events is not None
    assert fakes.calls[0] == ("get_element", {"element_id": "r1"})
    assert (events[-1]["answer"].answer, events[-1]["answer"].value) == ("Bad: 4.36 m².", 4.36)


def test_a_room_without_an_area_goes_to_the_agent(fakes: Fakes) -> None:
    fakes.intent = {**EMPTY, "intent": "room_area", "number": "1.13"}
    fakes.rooms = [RoomRef("r1", ("Bad",), "1.13", None, None, None)]
    assert _run() is None


def test_a_tool_error_goes_to_the_agent(fakes: Fakes) -> None:
    fakes.results["count_elements"] = ToolInputError("not a valid id")
    assert _run() is None


def test_questions_the_router_does_not_recognise_go_to_the_agent(fakes: Fakes) -> None:
    fakes.intent = {**EMPTY}
    assert _run() is None
    fakes.intent = None  # the router call failed
    assert _run() is None
    assert fakes.calls == []


def test_the_router_is_not_asked_when_the_fast_path_cannot_apply(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr(
        fast_path, "route", lambda question, settings, usage: asked.append(question)
    )
    assert _run("off") is None
    assert _run(selected=['room "Kitchen" (element_id e1)']) is None  # "this room"
    assert _run(documents=[*DOC, *DOC]) is None  # a count over two drawings
    assert asked == []


def test_room_ref_collects_every_way_a_room_is_written() -> None:
    # An IFC room: Name "119", LongName "KORIDOR"; the dataset writes "KORIDOR (119)".
    el = Element(id=uuid.UUID(int=1), kind="room", text="119", label="119", name="KORIDOR",
                 properties={"storey": "1.korrus", "area_m2": 63.8})  # fmt: skip
    ref = room_ref(el)
    assert ref.names == ("119", "KORIDOR", "KORIDOR (119)", "119 (119)")
    assert (ref.number, ref.storey, ref.unit, ref.area_m2) == ("119", "1.korrus", None, 63.8)
    # A drawing room: printed name and number, no storey.
    el = Element(id=uuid.UUID(int=2), kind="room", text="Bad", label="Bad",
                 name="room (Bad) 1.13", properties={"number": "1.13", "unit": "A"})  # fmt: skip
    ref = room_ref(el)
    assert (ref.number, ref.unit, ref.area_m2) == ("1.13", "A", None)
    assert "Bad" in ref.names


def test_a_storey_given_as_a_name_is_tried_as_a_storey(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Seen live: "the floor plan of 'Grundplan'" came back with name="Grundplan".
    fakes.intent = {**EMPTY, "intent": "count", "kind": "door", "name": "Grundplan"}

    def run_tool(name: str, args: dict[str, Any], ctx: ToolContext) -> str:
        fakes.calls.append((name, args))
        found = args.get("storey") == "Grundplan"
        doors = [_door(1, page=False), _door(2, page=False)] if found else []
        return json.dumps({"total": len(doors), "elements": doors})

    monkeypatch.setattr(fast_path, "run_tool", run_tool)
    events = _run()
    assert events is not None
    assert events[-1]["answer"].answer == "2 doors on Grundplan."
    assert [(c[1]["name"], c[1]["storey"]) for c in fakes.calls] == [
        ("Grundplan", None),
        (None, "Grundplan"),
    ]
    # The step shown is the call that found them.
    assert events[0]["input"]["storey"] == "Grundplan"


def test_the_default_answers_only_from_exact_elements(fakes: Fakes) -> None:
    # Measured on the preview (D-038): detections were wrong on 6 of 6 raster counts.
    settings = Settings(database_url="postgresql://unused", valkey_url="redis://unused")
    assert settings.fast_path == "exact"


def test_an_area_answer_is_labelled_on_the_plan() -> None:
    from app.domain.intents import Draft, Intent
    from app.qa.fast_path import plan_label

    apartment = Intent(intent="area_total", unit="A")
    assert plan_label(Draft("…", 78.4, "m2"), apartment) == "Apartment A · 78.4 m²"
    assert plan_label(Draft("…", 12.0, "m2"), Intent(intent="room_area")) == "12 m²"
    assert plan_label(Draft("…", 7.0, "count"), apartment) is None  # counts get no label
