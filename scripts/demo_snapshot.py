#!/usr/bin/env python3
"""Record a running local stack into the static demo's snapshot (D-059).

Usage (with `make up` running, no APP_PASSWORD set, documents uploaded and ready):
    python3 scripts/demo_snapshot.py [--url http://localhost:8080] [--out frontend/demo]
        [--questions frontend/src/lib/examples.json] [--documents ID,ID]

For every ready document it saves the detail, each page's image and elements, recorded
upscales, the 3D mesh and the IFC model, then asks each question about that document and
saves every event the answer streamed. `cd frontend && npm run build:demo` builds the demo
from it. Asking runs the real agent, so it uses the stack's Claude key. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------- pure parts (tested in demo_snapshot_test.py) ----------


def parse_sse(text: str) -> list[dict[str, str]]:
    """Every server-sent event in `text`, in order, as {"event", "data"}."""
    events = []
    for block in text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n"):
        event, data = "message", []
        for line in block.split("\n"):
            if line.startswith(":"):
                continue  # keepalive
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                event = value
            elif field == "data":
                data.append(value)
        if data:
            events.append({"event": event, "data": "\n".join(data)})
    return events


def asset_path(document_id: str, kind: str, index: int | None = None) -> str:
    """Where a recorded file lives; the same layout as assetPath in the frontend."""
    folder = f"documents/{document_id}"
    names = {"mesh": "mesh.json", "ifc": "model.ifc"}
    if kind in names:
        return f"{folder}/{names[kind]}"
    extension = "png" if kind == "page" else "json"
    return f"{folder}/{kind}-{index}.{extension}"


def mesh_body(body: bytes, content_encoding: str | None) -> bytes:
    """The mesh JSON, unzipped when the API sent it gzipped (static hosts zip it again)."""
    return gzip.decompress(body) if content_encoding == "gzip" else body


def snapshot_json(
    *,
    recorded_at: str,
    health: dict[str, Any],
    documents: list[dict[str, Any]],
    upscales: dict[str, list[int]],
    recordings: list[dict[str, Any]],
) -> dict[str, Any]:
    """snapshot.json, as the Snapshot type in frontend/src/demo/snapshot.ts reads it."""
    return {
        "recorded_at": recorded_at,
        "health": health,
        "documents": documents,
        "upscales": {d["id"]: upscales.get(d["id"], []) for d in documents},
        "recordings": recordings,
    }


# ---------- talking to the stack ----------


class Stack:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def raw(self, path: str, body: Any = None, timeout: float = 120) -> tuple[bytes, str | None]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            method="GET" if body is None else "POST",
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get("Content-Encoding")

    def data(self, path: str, body: Any = None, timeout: float = 120) -> Any:
        envelope = json.loads(self.raw(path, body, timeout)[0])
        if not envelope.get("ok"):
            raise RuntimeError(f"{path}: {envelope.get('error')}")
        return envelope["data"]


def record(stack: Stack, out: Path, questions: list[str], only: set[str] | None) -> None:
    session = stack.data("/api/session")
    if session["required"] and not session["authenticated"]:
        sys.exit("The stack asks for a login. Record from a local stack without APP_PASSWORD.")

    documents: list[dict[str, Any]] = []
    upscales: dict[str, list[int]] = {}
    recordings: list[dict[str, Any]] = []
    for listed in stack.data("/api/documents"):
        if listed["status"] != "ready" or (only and listed["id"] not in only):
            continue
        doc_id = listed["id"]
        doc = stack.data(f"/api/documents/{doc_id}")
        print(f"{doc['filename']}: {len(doc['pages'])} page(s)")
        documents.append(doc)

        def save(path: str, body: bytes) -> None:
            target = out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)

        for page in doc["pages"]:
            i = page["index"]
            save(
                asset_path(doc_id, "page", i),
                stack.raw(f"/api/documents/{doc_id}/pages/{i}/image")[0],
            )
            elements = stack.data(f"/api/documents/{doc_id}/elements?page={i}")
            save(asset_path(doc_id, "elements", i), json.dumps(elements).encode())
            if page.get("upscale"):  # already redrawn, so this returns the cached result
                result = stack.data(f"/api/documents/{doc_id}/pages/{i}/upscale", {}, 1500)
                save(asset_path(doc_id, "upscale", i), json.dumps(result).encode())
                upscales.setdefault(doc_id, []).append(i)
        if doc["has_model"]:
            save(asset_path(doc_id, "mesh"), mesh_body(*stack.raw(f"/api/documents/{doc_id}/mesh")))
        if doc["has_ifc"]:
            save(asset_path(doc_id, "ifc"), stack.raw(f"/api/documents/{doc_id}/model.ifc")[0])

        context = {"document_id": doc_id, "page_index": 0, "element_id": None, "element_ids": []}
        for question in questions:
            print(f"  asking: {question}")
            ask = {"question": question, "document_ids": [doc_id], "context": context}
            events = parse_sse(stack.raw("/api/ask", ask, 600)[0].decode())
            if not any(e["event"] == "answer" for e in events):
                print("    no answer; recorded anyway, the demo shows what the stack said")
            recordings.append({"question": question, "document_ids": [doc_id], "events": events})

    if not documents:
        sys.exit("No ready documents to record. Upload some with the stack running first.")
    snapshot = snapshot_json(
        recorded_at=datetime.date.today().isoformat(),
        health=stack.data("/api/health"),
        documents=documents,
        upscales=upscales,
        recordings=recordings,
    )
    (out / "snapshot.json").write_text(json.dumps(snapshot, indent=1))
    print(f"Recorded {len(documents)} document(s), {len(recordings)} answer(s) into {out}")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--out", type=Path, default=root / "frontend" / "demo")
    parser.add_argument("--questions", type=Path, default=root / "frontend/src/lib/examples.json")
    parser.add_argument("--documents", help="comma-separated ids; default every ready document")
    args = parser.parse_args()

    # A fresh snapshot replaces the old one; nothing else lives in the demo folder.
    shutil.rmtree(args.out / "documents", ignore_errors=True)
    args.out.mkdir(parents=True, exist_ok=True)
    only = set(args.documents.split(",")) if args.documents else None
    try:
        record(Stack(args.url), args.out, json.loads(args.questions.read_text()), only)
    except urllib.error.URLError as error:
        sys.exit(f"Cannot reach the stack at {args.url} ({error.reason}). Is `make up` running?")


if __name__ == "__main__":
    main()
