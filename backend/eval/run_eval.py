"""Run an eval set against a running API and report accuracy, verified rate and cost
(D-019, #98).

    uv run python -m eval.run_eval ../.local/eval.jsonl --api http://localhost:8000 \\
        --out ../.local/run-kimi.jsonl --price kimi-k3-1-pro=IN,OUT

Build the eval set from the dataset with `eval.build_eval_set`. Each JSONL line:
{"question", "expected", "type", "unit", "source", "path", "document_ids"}. Counts must
match exactly, areas, lengths and volumes within 2%; text answers are not scored.

`--out` writes one line per question (the question, the reply and what it used), so two
runs can be compared. `--price` gives a model's price in dollars per million tokens
(input, output, then optionally cached input read and written); see eval/prices.py.
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from eval.cost_report import cost_lines, error_line, method_line
from eval.outcome import outcome
from eval.prices import PRICES, parse_price
from eval.report import Result, summarize

MARKS = {True: "PASS", False: "FAIL", None: "----"}
SHOW_CHARS = 120  # long text answers would flood the log


def _short(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= SHOW_CHARS else text[: SHOW_CHARS - 3] + "..."


def ask(api: str, question: str, document_ids: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The answer or error of one question, and the stats of its `done` event."""
    body = {"question": question, "document_ids": document_ids}
    event, reply, stats = "", {}, {}
    with httpx.stream("POST", f"{api}/api/ask", json=body, timeout=900) as response:
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: ") and event in ("answer", "error"):
                reply = json.loads(line[6:])
            elif line.startswith("data: ") and event == "done":
                stats = json.loads(line[6:])
    return reply, stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", type=Path)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--out", type=Path, help="write one JSON line per question here")
    parser.add_argument("--price", action="append", default=[], type=parse_price,
                        metavar="MODEL=IN,OUT", help="dollars per million tokens")  # fmt: skip
    args = parser.parse_args()
    prices = {**PRICES, **dict(args.price)}

    rows = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    results: list[Result] = []
    written: list[str] = []
    for row in rows:
        try:
            reply, stats = ask(args.api, row["question"], row.get("document_ids", []))
        except httpx.HTTPError as exc:  # one lost connection must not lose the run
            reply, stats = {"code": f"http_{type(exc).__name__}"}, {}
        result = outcome(row, reply, stats, prices)
        results.append(result)
        got = reply.get("answer") or reply.get("code") or "no answer"
        cost = "" if result.cost_usd is None else f", ${result.cost_usd:.4f}"
        print(f"{MARKS[result.correct]}  [{row['source']}/{row['type']}] {row['question']}")
        print(f"      expected {_short(row['expected'])}, value {reply.get('value')!r}: "
              f"{_short(got)}")  # fmt: skip
        print(f"      {result.tokens_in:,} in + {result.tokens_out:,} out tokens, "
              f"{result.steps} steps, {result.seconds:.1f} s{cost}")  # fmt: skip
        line = {**row, "reply": reply, "stats": stats, "result": asdict(result)}
        written.append(json.dumps(line, ensure_ascii=False))
        if args.out:  # rewritten after every question, so a stopped run keeps its results
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text("\n".join(written) + "\n")
    print()
    print(
        "\n".join(
            [*summarize(results), *cost_lines(results), method_line(results), error_line(results)]
        )
    )


if __name__ == "__main__":
    main()
