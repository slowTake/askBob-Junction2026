from eval.report import Result, summarize


def test_accuracy_by_source_and_type_skips_unscored() -> None:
    results = [
        Result("cubicasa5k", "count", correct=True, verified=True),
        Result("cubicasa5k", "count", correct=False, verified=False),
        Result("swiss_dwellings", "area", correct=True, verified=False),
        Result("ifc_bench", "text", correct=None, verified=True),
    ]
    lines = summarize(results)
    # Scored: 3 questions, 2 correct. Verified counts all 4 answers: 2 of 4.
    assert lines[0] == "overall: 2/3 correct (67%), verified 2/4 (50%), not scored 1"
    assert "  cubicasa5k / count: 1/2 correct (50%), verified 1/2 (50%)" in lines
    assert "  swiss_dwellings / area: 1/1 correct (100%), verified 0/1 (0%)" in lines
    assert "  ifc_bench / text: not scored, verified 1/1 (100%)" in lines


def test_groups_are_sorted() -> None:
    results = [Result("b", "count", True, True), Result("a", "count", True, True)]
    assert summarize(results)[1:] == [
        "  a / count: 1/1 correct (100%), verified 1/1 (100%)",
        "  b / count: 1/1 correct (100%), verified 1/1 (100%)",
    ]


def test_empty_run() -> None:
    assert summarize([]) == ["overall: 0/0 correct (0%), verified 0/0 (0%), not scored 0"]
