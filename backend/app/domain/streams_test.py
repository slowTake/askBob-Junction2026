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
    a = answer_cache_key("How wide is  the door?", ["d1@1", "d2@1"], "m", 1)
    b = answer_cache_key("how wide is the door?", ["d2@1", "d1@1"], "m", 1)
    assert a == b


def test_cache_key_changes_with_document_version_model_or_answer_format() -> None:
    base = answer_cache_key("q", ["d1@1"], "m", 1)
    assert base != answer_cache_key("q", ["d1@2"], "m", 1)
    assert base != answer_cache_key("q", ["d1@1"], "other", 1)
    # A cached answer in an older format must not be served after the format changes.
    assert base != answer_cache_key("q", ["d1@1"], "m", 2)


def test_cache_key_changes_with_what_the_user_is_looking_at() -> None:
    # "How big is this?" about the kitchen must not replay the answer about a bedroom.
    kitchen = answer_cache_key("how big is this?", ["d1@1"], "m", 1, context="selected e1")
    bedroom = answer_cache_key("how big is this?", ["d1@1"], "m", 1, context="selected e2")
    assert kitchen != bedroom
    assert kitchen != answer_cache_key("how big is this?", ["d1@1"], "m", 1)
