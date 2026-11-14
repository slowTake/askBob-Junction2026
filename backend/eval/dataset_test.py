from typing import Any

from eval.dataset import eval_rows, sample_paths, source_of


def _row(path: str, answer: Any = 1, kind: str = "count") -> dict[str, Any]:
    unit = "count" if kind == "count" else None
    return {"path": path, "question": f"Q about {path}", "answer": answer, "unit": unit,
            "type": kind}  # fmt: skip


def test_source_is_the_folder_under_data() -> None:
    assert source_of("data/cubicasa5k/colorful-11397.png") == "cubicasa5k"
    assert source_of("data/opening_design/a/b/sheet.pdf") == "opening_design"


def test_sample_takes_at_most_n_distinct_paths_per_source() -> None:
    rows = [_row("data/a/1.png"), _row("data/a/1.png"), _row("data/a/2.png"),
            _row("data/a/3.png"), _row("data/b/1.pdf")]  # fmt: skip
    paths = sample_paths(rows, per_source=2)
    # Source a has 3 distinct paths, so 2 of them; source b has 1.
    assert len(paths) == 3
    assert len(set(paths)) == 3
    assert sum(p.startswith("data/a/") for p in paths) == 2
    assert "data/b/1.pdf" in paths


def test_sample_is_deterministic_and_independent_of_row_order() -> None:
    rows = [_row(f"data/a/{i}.png") for i in range(20)]
    assert sample_paths(rows, per_source=5) == sample_paths(rows[::-1], per_source=5)


def test_sample_grows_without_reshuffling() -> None:
    # Raising the sample size keeps the drawings already uploaded for a smaller one.
    rows = [_row(f"data/a/{i}.png") for i in range(20)]
    assert set(sample_paths(rows, per_source=3)) <= set(sample_paths(rows, per_source=6))


def test_eval_rows_keep_only_uploaded_paths_and_carry_scoring_fields() -> None:
    rows = [_row("data/a/1.png", answer=13), _row("data/b/2.pdf", answer=4.4, kind="area")]
    out = eval_rows(rows, {"data/b/2.pdf": "doc-2"})
    assert out == [
        {
            "question": "Q about data/b/2.pdf",
            "expected": 4.4,
            "type": "area",
            "unit": None,
            "source": "b",
            "path": "data/b/2.pdf",
            "document_ids": ["doc-2"],
        }
    ]


def test_eval_rows_cap_questions_per_drawing_in_file_order() -> None:
    rows = [_row("data/a/1.png", answer=i) for i in range(5)] + [_row("data/a/2.png", answer=9)]
    out = eval_rows(rows, {"data/a/1.png": "d1", "data/a/2.png": "d2"}, per_drawing=2)
    # The first two questions about 1.png, then the only one about 2.png.
    assert [(r["path"], r["expected"]) for r in out] == [
        ("data/a/1.png", 0),
        ("data/a/1.png", 1),
        ("data/a/2.png", 9),
    ]
