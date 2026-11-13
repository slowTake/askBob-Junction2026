"""Run a question set against a running API and report accuracy and verification rate.

    uv run python -m eval.run_eval eval/questions.example.jsonl --api http://localhost:8000

Each JSONL line: {"question": "...", "expected": "900", "document_ids": ["..."]}.
Put Stoa's example questions in a JSONL file like this to track progress.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from eval.scoring import is_correct


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
    correct = verified = 0
    for row in rows:
        result = ask(args.api, row["question"], row.get("document_ids", []))
        answer = str(result.get("answer", ""))
        ok = is_correct(str(row["expected"]), answer)
        correct += ok
        verified += bool(result.get("verified"))
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {row['question']}\n      expected {row['expected']!r}, got {answer!r}")
    total = max(len(rows), 1)
    print(
        f"\naccuracy {correct}/{len(rows)} = {correct / total:.0%}, verified {verified / total:.0%}"
    )


if __name__ == "__main__":
    main()
