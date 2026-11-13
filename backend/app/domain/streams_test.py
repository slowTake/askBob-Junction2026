from app.domain.streams import answer_cache_key, sse


def test_sse_frame() -> None:
    # SSE spec: "event:" line, "data:" line, blank line terminates the event.
    assert sse("step", {"tool": "find_elements"}) == (
        'event: step\ndata: {"tool":"find_elements"}\n\n'
    )


def test_sse_escapes_newlines_inside_data() -> None:
    frame = sse("answer", {"text": "a\nb"})
    assert frame.count("\n") == 3  # event line, data line, blank line


def test_cache_key_ignores_case_spacing_and_document_order() -> None:
    a = answer_cache_key("How wide is  the door?", ["d1@1", "d2@1"], "m")
    b = answer_cache_key("how wide is the door?", ["d2@1", "d1@1"], "m")
    assert a == b


def test_cache_key_changes_with_document_version_or_model() -> None:
    base = answer_cache_key("q", ["d1@1"], "m")
    assert base != answer_cache_key("q", ["d1@2"], "m")
    assert base != answer_cache_key("q", ["d1@1"], "other")
