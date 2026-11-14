"""Run an eval set against a running API and report accuracy and verified rate (D-019).

    uv run python -m eval.run_eval ../.local/eval.jsonl --api http://localhost:8000

Build the eval set from the dataset with `eval.build_eval_set`. Each JSONL line:
{"question", "expected", "type", "unit", "source", "path", "document_ids"}. Counts must
match exactly, areas, lengths and volumes within 2%; text answers are not scored.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from eval.report import Result, summarize
from eval.scoring import score

MARKS = {True: "PASS", False: "FAIL", None: "----"}
SHOW_CHARS = 120  # long text answers would flood the log


def _short(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= SHOW_CHARS else text[: SHOW_CHARS - 3] + "..."


def ask(api: str, question: str, document_ids: list[str]) -> dict[str, Any]:
    body = {"question": question, "document_ids": document_ids}
    event, result = "", {"error": "no answer"}
    with httpx.stream("POST", f"{api}/api/ask", json=body, timeout=600) as response:
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: ") and event in ("answer", "error"):
                result = json.loads(line[6:])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", type=Path)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    results: list[Result] = []
    for row in rows:
        result = ask(args.api, row["question"], row.get("document_ids", []))
        value = result.get("value")
        correct = score(row["type"], row["expected"], value)
        results.append(Result(row["source"], row["type"], correct, bool(result.get("verified"))))
        got = result.get("answer") or result.get("code") or result.get("error")
        expected = _short(row["expected"])
        print(f"{MARKS[correct]}  [{row['source']}/{row['type']}] {row['question']}")
        print(f"      expected {expected}, value {value!r}: {_short(got)}")
    print()
    print("\n".join(summarize(results)))


if __name__ == "__main__":
    main()
