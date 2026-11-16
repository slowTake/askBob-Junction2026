"""Score the Redrawn view of colorful-34 against its hand-made truth (#131, D-049).

    uv run python -m eval.redraw_bench            # recorded OCR and vision answers, no network
    uv run python -m eval.redraw_bench --live     # read the page now, write nothing
    uv run python -m eval.redraw_bench --record   # read the page now and save the readings

The page is annotated exactly as the app's image reader does it (`annotate_page` on the
page's ink, with fills and red labels taken off, D-050), fed the recorded OCR words and
vision answer, and turned into what the Redrawn view draws (`redraw_elements.py`). A live
reading runs the app's local OCR (RapidOCR) on the page with its fills divided out, and
asks the vision service only when `VISION_URL` is set and answers. The upscale (vision
model) pass on top of ingest is not run here.

Recordings, next to the image:
  colorful-34.ocr.json     {"engine": "rapid", "words": [{"bbox", "text", "confidence"}]}
  colorful-34.vision.json  {"status": "used", "data": <the service's answer>}, or just
                           {"status": "unavailable" | "failed" | "skipped"}
"""

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.config import Settings
from app.domain.ocr_wire import parse_words, words_to_json
from app.domain.tokens import Word
from app.domain.vision import Parsed, parse
from app.ingest.annotate import annotate_page
from app.ingest.image_reader import _on_white
from app.ingest.ink import ColourLayers, separate_colours
from app.ingest.ocr import ocr_words
from app.ingest.rooms import Gray
from eval.redraw_elements import sheet_from_elements
from eval.redraw_render import Mask, MaskScore, mask_scores, near_share, wall_mask
from eval.redraw_score import (
    OpeningScore,
    RoomScore,
    TextScore,
    match_openings,
    match_rooms,
    match_texts,
)
from eval.redraw_sheet import Sheet, load_sheet

BENCH = Path(__file__).parent / "redraw_bench"
IMAGE = BENCH / "colorful-34.png"
TRUTH = BENCH / "colorful-34.truth.json"
OCR = BENCH / "colorful-34.ocr.json"
VISION = BENCH / "colorful-34.vision.json"

# Tolerances as shares of the page width, set on the benchmark's 482 px.
# Walls and ink: 2 px. A scanned wall line is 2-4 px wide and the truth is drawn by hand
# on it, so a redraw one or two pixels beside it is on the line; 3 px would already
# accept a parallel line half a thin wall away.
WALL_TOLERANCE = 2 / 482
# Openings, room labels and texts, by their middle: 4 px. Text is 5-8 px tall, so 4 px is
# about half a letter height: a box centre from OCR lands within it, the next word does not.
POSITION_TOLERANCE = 4 / 482
VISION_TIMEOUT_S = 90


@dataclass(frozen=True)
class BenchReport:
    walls: MaskScore
    openings: OpeningScore
    rooms: RoomScore
    texts: TextScore
    # The page's ink against the truth: how good the ink the redraw is built from is.
    ink_finds_walls: float  # share of truth wall pixels the page's ink mask finds
    ink_off_walls: float  # share of ink pixels away from any truth wall (fills, text, noise)
    # The redraw against the page's ink, no truth needed (#132). Walls only for now.
    ink_redrawn: float  # share of the page's ink the redraw's walls lie on ("missed": 1 - it)
    redraw_on_ink: float  # share of the redraw's walls on ink ("added": 1 - it)
    wall_tolerance_px: float
    position_tolerance_px: float


def report(sheet: Sheet, truth: Sheet, ink: Mask, width: int, height: int) -> BenchReport:
    """Every number of the benchmark, for the redraw `sheet` on a `width` x `height` page.

    `ink` is the page's ink mask. It is scored against the truth walls on its own: the
    redraw's walls are built from it, so a better ink mask should lift the wall scores.
    Ink off walls also counts text and fixtures, which are real ink but not walls, so it
    never reaches 0; it is read as a change between runs. The redraw is also scored
    against the ink with no truth, the score the app can show on any page (#132); only
    its walls are drawn as pixels so far, so "ink redrawn" stays low until openings and
    text are too.
    """
    wall_px = WALL_TOLERANCE * width
    position_px = POSITION_TOLERANCE * width
    redrawn = wall_mask(sheet.walls, width, height)
    truth_walls = wall_mask(truth.walls, width, height)
    return BenchReport(
        walls=mask_scores(redrawn, truth_walls, wall_px),
        openings=match_openings(sheet.openings, truth.openings, position_px),
        rooms=match_rooms(sheet.rooms, truth.rooms, position_px),
        texts=match_texts(sheet.texts, truth.texts, position_px),
        ink_finds_walls=near_share(truth_walls, ink, wall_px),
        ink_off_walls=1 - near_share(ink, truth_walls, wall_px) if ink.any() else 0.0,
        ink_redrawn=near_share(ink, redrawn, wall_px),
        redraw_on_ink=near_share(redrawn, ink, wall_px),
        wall_tolerance_px=wall_px,
        position_tolerance_px=position_px,
    )


def table(r: BenchReport) -> str:
    def pct(v: float) -> str:
        return f"{v:6.1%}"

    def of(n: int, total: int) -> str:
        return f"{n:3d}/{total:<3d}"

    o, rm, t = r.openings, r.rooms, r.texts
    rows = [
        f"tolerance  walls/ink {r.wall_tolerance_px:.1f} px"
        f", positions {r.position_tolerance_px:.1f} px",
        f"walls      recall {pct(r.walls.recall)}  precision {pct(r.walls.precision)}"
        f"  F1 {pct(r.walls.f1)}",
        f"openings   found {of(o.found.matched, o.found.truth)} (drawn {o.found.predicted})"
        f"  P {pct(o.found.precision)}  R {pct(o.found.recall)}"
        f"  swings {of(o.swings_ok, o.swings_checked)}",
        f"rooms      named {of(rm.named.matched, rm.named.truth)} (drawn {rm.named.predicted})"
        f"  P {pct(rm.named.precision)}  R {pct(rm.named.recall)}"
        f"  outlined {of(rm.outlined, rm.named.truth)}",
        f"texts      found {of(t.found.matched, t.found.truth)} (drawn {t.found.predicted})"
        f"  P {pct(t.found.precision)}  R {pct(t.found.recall)}",
        f"           exact {of(t.exact, t.found.truth)}  digits {of(t.digits, t.found.truth)}"
        f"  kind {of(t.kind_ok, t.found.matched)}  rotation {of(t.rotation_ok, t.found.matched)}",
        f"ink        finds walls {pct(r.ink_finds_walls)}  off walls {pct(r.ink_off_walls)}",
        f"redraw     ink redrawn {pct(r.ink_redrawn)}  on ink {pct(r.redraw_on_ink)}",
    ]
    return "\n".join(rows)


def page(path: Path) -> tuple[ColourLayers, bytes]:
    """The page's colour layers and PNG, prepared as the image reader prepares them.

    The benchmark image is far below the reader's size limit, so it is never resized.
    """
    with Image.open(path) as opened:
        image = _on_white(opened)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return separate_colours(np.asarray(image, dtype=np.uint8)), buffer.getvalue()


def redraw(gray: Gray, words: list[Word], vision: Parsed | None) -> Sheet:
    """What the Redrawn view shows for the page after ingest (no upscale pass)."""
    elements, _, _ = annotate_page(gray, words, "ocr", None, vision=vision)
    return sheet_from_elements(elements, gray.shape[1])


def recorded_words(raw: Any) -> list[Word]:
    words = parse_words(raw)
    if words is None:
        raise ValueError("the OCR recording is malformed")
    return words


def recorded_vision(raw: Any) -> Parsed | None:
    """The parsed answer the reader would have had: None unless the service answered."""
    if not isinstance(raw, dict) or not isinstance(raw.get("status"), str):
        raise ValueError("the vision recording is malformed")
    return parse(raw.get("data")) if raw["status"] == "used" else None


def ask_vision(png: bytes, url: str | None) -> dict[str, Any]:
    """The vision service's answer as `vision_client.analyse_page` gets it, unparsed."""
    if not url:
        return {"status": "unavailable"}
    request = urllib.request.Request(
        url.rstrip("/") + "/analyse",
        data=png,
        headers={"Content-Type": "image/png"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=VISION_TIMEOUT_S) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError:
        return {"status": "failed"}
    except urllib.error.URLError as exc:
        timed_out = isinstance(exc.reason, TimeoutError)
        return {"status": "failed" if timed_out else "unavailable"}
    except (OSError, ValueError):
        return {"status": "failed"}
    if not isinstance(body, dict) or body.get("ok") is not True:
        return {"status": "failed"}
    data = body.get("data")
    if isinstance(data, dict) and data.get("method") == "skipped_too_large":
        return {"status": "skipped"}
    return {"status": "used", "data": data}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, Any]) -> None:
    """One key per line, and one list item (an OCR word) per line, so a diff stays readable."""

    def value(v: Any) -> str:
        if isinstance(v, list) and v:
            return "[\n  " + ",\n  ".join(json.dumps(i, ensure_ascii=False) for i in v) + "\n ]"
        return json.dumps(v, ensure_ascii=False)

    body = ",\n".join(f" {json.dumps(k)}: {value(v)}" for k, v in data.items())
    path.write_text("{\n" + body + "\n}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="read the page now, save nothing")
    mode.add_argument("--record", action="store_true", help="read the page now and save it")
    args = parser.parse_args()

    layers, png = page(IMAGE)
    height, width = layers.ink_page.shape
    if args.live or args.record:
        settings = Settings.model_construct()  # defaults only: no database, OCR runs here
        ocr = {
            "engine": "rapid",
            "words": words_to_json(ocr_words(layers.ocr_page, settings.ocr_langs)),
        }
        vision = ask_vision(png, os.environ.get("VISION_URL"))
        if args.record:
            _write(OCR, ocr)
            _write(VISION, vision)
            print(f"recorded {len(ocr['words'])} words to {OCR.name}, "
                  f"vision {vision['status']} to {VISION.name}")  # fmt: skip
    else:
        missing = [p.name for p in (OCR, VISION) if not p.exists()]
        if missing:
            print(f"no recording ({', '.join(missing)}): run with --record", file=sys.stderr)
            return 2
        ocr, vision = _read(OCR), _read(VISION)

    if not TRUTH.exists():
        print(f"no truth file ({TRUTH.name}): nothing to score against", file=sys.stderr)
        return 2
    truth = load_sheet(_read(TRUTH), width, height)
    sheet = redraw(layers.ink_page, recorded_words(ocr), recorded_vision(vision))
    print(f"{IMAGE.name} {width}x{height}  words {len(ocr['words'])}  vision {vision['status']}")
    print(f"drawn      walls {len(sheet.walls)}  openings {len(sheet.openings)}"
          f"  rooms {len(sheet.rooms)}  texts {len(sheet.texts)}")  # fmt: skip
    print(table(report(sheet, truth, layers.ink, width, height)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
