"""Turn the dataset's questions.jsonl into our eval set. Pure; used by build_eval_set.py.

A questions.jsonl row: {"path", "question", "answer", "unit", "type"}, where `path` is
`data/<source>/<file>`.
"""

import hashlib
from collections import defaultdict
from typing import Any


def source_of(path: str) -> str:
    """ "data/cubicasa5k/x.png" -> "cubicasa5k"."""
    return path.split("/")[1]


def sample_paths(rows: list[dict[str, Any]], per_source: int) -> list[str]:
    """At most `per_source` distinct drawings per source.

    Paths are ranked by a hash of the path, so the sample does not depend on row order,
    and a larger sample contains the smaller one (drawings already uploaded are reused).
    """
    by_source: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_source[source_of(row["path"])].add(row["path"])
    sample: list[str] = []
    for source in sorted(by_source):
        ranked = sorted(by_source[source], key=lambda p: hashlib.sha256(p.encode()).hexdigest())
        sample.extend(ranked[:per_source])
    return sample


def eval_rows(
    rows: list[dict[str, Any]], document_ids: dict[str, str], per_drawing: int | None = None
) -> list[dict[str, Any]]:
    """One eval row per question about an uploaded drawing (`document_ids`: path -> id),
    at most `per_drawing` per drawing, in file order."""
    taken: dict[str, int] = defaultdict(int)
    out: list[dict[str, Any]] = []
    for row in rows:
        path = row["path"]
        if path not in document_ids or (per_drawing is not None and taken[path] >= per_drawing):
            continue
        taken[path] += 1
        out.append(
            {
                "question": row["question"],
                "expected": row["answer"],
                "type": row["type"],
                "unit": row["unit"],
                "source": source_of(path),
                "path": path,
                "document_ids": [document_ids[path]],
            }
        )
    return out
