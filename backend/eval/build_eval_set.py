"""Build an eval set from the dataset: upload a sample of drawings, write eval JSONL (D-019).

    uv run python -m eval.build_eval_set ~/Downloads/junction-dataset-preview \\
        --per-source 3 --per-drawing 4 --out ../.local/eval.jsonl

Point it at a local stack (`make up-local`), not the shared database. A drawing that is
already uploaded (same file name and size) is reused; a failed one is re-ingested.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from eval.dataset import eval_rows, sample_paths, source_of

POLL_S = 2.0
DONE = ("ready", "failed")


def _data(response: httpx.Response) -> Any:
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"{response.request.url}: {body.get('error')}")
    return body["data"]


def _document_for(client: httpx.Client, file: Path, existing: list[dict[str, Any]]) -> str:
    size = file.stat().st_size
    for doc in existing:
        if doc["filename"] == file.name and doc["size_bytes"] == size:
            if doc["status"] == "failed":
                _data(client.post(f"/api/documents/{doc['id']}/reingest"))
            return str(doc["id"])
    with file.open("rb") as handle:
        return str(_data(client.post("/api/documents", files={"file": (file.name, handle)}))["id"])


def _wait(client: httpx.Client, doc_id: str, timeout_s: float) -> str:
    deadline = time.monotonic() + timeout_s
    while True:
        status = str(_data(client.get(f"/api/documents/{doc_id}"))["status"])
        if status in DONE or time.monotonic() > deadline:
            return status
        time.sleep(POLL_S)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset", type=Path, help="folder with questions.jsonl and data/")
    parser.add_argument("--out", type=Path, required=True, help="eval JSONL to write")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--per-source", type=int, default=3, help="drawings per source")
    parser.add_argument("--per-drawing", type=int, default=None, help="questions per drawing")
    parser.add_argument("--timeout", type=float, default=900, help="seconds to wait per drawing")
    args = parser.parse_args()

    lines = (args.dataset / "questions.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    paths = sample_paths(rows, args.per_source)
    ids: dict[str, str] = {}
    with httpx.Client(base_url=args.api, timeout=300) as client:
        existing = _data(client.get("/api/documents"))
        for path in paths:
            try:
                ids[path] = _document_for(client, args.dataset / path, existing)
            except (OSError, RuntimeError, httpx.HTTPError) as exc:
                print(f"skip {path}: {exc}", file=sys.stderr)
        for path, doc_id in ids.items():
            status = _wait(client, doc_id, args.timeout)
            print(f"{status:<10} {source_of(path):<16} {path}")

    out = eval_rows(rows, ids, args.per_drawing)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    print(f"wrote {len(out)} questions about {len(ids)} drawings to {args.out}")


if __name__ == "__main__":
    main()
