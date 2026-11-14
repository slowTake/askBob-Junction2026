"""The agent is told what the user is looking at and what they selected on the plan."""

from app.qa.prompts import (
    SelectedElement,
    budget_note,
    scope_message,
    selected_note,
    selected_notes,
    viewing_note,
)

DOCS: list[dict[str, object]] = [
    {"id": "d1", "filename": "plan.dxf", "kind": "dxf", "page_count": 1},
]


def test_without_context_the_message_lists_documents_and_the_question() -> None:
    assert scope_message("How many rooms?", DOCS) == (
        "Documents in scope:\n- d1: plan.dxf (dxf, 1 pages)\n\nQuestion: How many rooms?"
    )


def test_the_viewed_page_and_selected_element_come_before_the_question() -> None:
    message = scope_message(
        "How big is this?",
        DOCS,
        viewing="page 1 of plan.dxf (document_id d1, page_index 0)",
        selected=['room "Kitchen" (element_id e1, page_index 0)'],
    )
    assert message == (
        "Documents in scope:\n- d1: plan.dxf (dxf, 1 pages)\n\n"
        "The user is looking at page 1 of plan.dxf (document_id d1, page_index 0).\n"
        'The user selected room "Kitchen" (element_id e1, page_index 0) on the plan. '
        '"This", "here" and "it" refer to it: call get_element for its details.\n\n'
        "Question: How big is this?"
    )


def test_viewing_note_names_the_page_like_the_ui() -> None:
    # page_index is 0-based for tools; the UI says "page 2 of 3"
    assert viewing_note("plan.pdf", "d1", 1, 3, "Level 1") == (
        'page 2 of 3 ("Level 1") of plan.pdf (document_id d1, page_index 1)'
    )
    assert viewing_note("plan.pdf", "d1", 0, 1, None) == (
        "page 1 of 1 of plan.pdf (document_id d1, page_index 0)"
    )


def test_selected_note_names_the_element_and_where_it_is() -> None:
    assert selected_note("room", "Kitchen", "e1", 0) == (
        'room "Kitchen" (element_id e1, page_index 0)'
    )
    assert selected_note("door", None, "e2", None) == "door (element_id e2)"


def test_the_step_budget_comes_before_the_question() -> None:
    assert scope_message("How many rooms?", DOCS, tool_rounds=11) == (
        "Documents in scope:\n- d1: plan.dxf (dxf, 1 pages)\n\n"
        + budget_note(11)
        + "\n\nQuestion: How many rooms?"
    )


def test_budget_note_counts_rounds_and_asks_for_an_early_answer() -> None:
    note = budget_note(11)
    assert note.startswith("You have at most 11 rounds of tool calls")
    assert "1 round of tool calls" in budget_note(1)  # singular


def test_several_selected_elements_are_listed() -> None:
    message = scope_message(
        "Which is bigger?",
        DOCS,
        selected=[
            'room "Kitchen" (element_id e1, page_index 0)',
            'room "WC" (element_id e2, page_index 0)',
        ],
    )
    assert message == (
        "Documents in scope:\n- d1: plan.dxf (dxf, 1 pages)\n\n"
        "The user selected these elements on the plan:\n"
        '- room "Kitchen" (element_id e1, page_index 0)\n'
        '- room "WC" (element_id e2, page_index 0)\n'
        '"These", "them" and "the selected ones" refer to them: '
        "call get_element for each one's details.\n\n"
        "Question: Which is bigger?"
    )


def test_selected_notes_keep_click_order_and_skip_what_is_not_in_scope() -> None:
    found = {
        "e1": SelectedElement("e1", "d1", "room", "Kitchen", 0),
        "e2": SelectedElement("e2", "d1", "door", None, None),
        "e9": SelectedElement("e9", "d2", "room", "Sauna", 0),  # a document not in scope
    }
    # Clicked e2, then e1, then e9, then one that no longer exists.
    assert selected_notes(["e2", "e1", "e9", "gone"], found, {"d1"}) == [
        "door (element_id e2)",
        'room "Kitchen" (element_id e1, page_index 0)',
    ]
    assert selected_notes([], found, {"d1"}) == []
