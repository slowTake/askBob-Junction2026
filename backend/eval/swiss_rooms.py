"""Score room outlines read from Swiss PNGs against the same floor's DXF (D-024).

    uv run python -m eval.swiss_rooms ~/Downloads/junction-dataset-preview/data/swiss_dwellings

Each swiss_dwellings floor ships as PNG, PDF and DXF. The DXF reader gives the truth
(room numbers and exact areas); the image reader, exactly as the app runs it (vision
service off), gives the PNG's rooms. Per floor and in total:
  named     the room's number was read and linked to a printed room name
  outlined  ...and the room got an outline
  area_ok   ...whose measured area (physical scale: DPI + printed "1:100") is within 5%
Needs the dataset, so it isn't part of the test suite.
"""

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.ingest.dxf_reader import read_dxf
from app.ingest.image_reader import read_image

AREA_TOLERANCE = 0.05


@dataclass(frozen=True)
class FloorScore:
    rooms: int
    named: int
    outlined: int
    area_ok: int

    def __add__(self, other: "FloorScore") -> "FloorScore":
        return FloorScore(
            self.rooms + other.rooms,
            self.named + other.named,
            self.outlined + other.outlined,
            self.area_ok + other.area_ok,
        )


def score_floor(truth: dict[str, float], traced: dict[str, float | None]) -> FloorScore:
    """`truth`: number -> DXF area. `traced`: number -> measured m² (None: no outline)."""
    named = [n for n in truth if n in traced]
    outlined = [n for n in named if traced[n] is not None]
    area_ok = [n for n in outlined if abs((traced[n] or 0) - truth[n]) <= AREA_TOLERANCE * truth[n]]
    return FloorScore(len(truth), len(named), len(outlined), len(area_ok))


def _truth(dxf: Path, settings: Settings) -> dict[str, float]:
    page = read_dxf(dxf, settings, lambda stage, f: None).pages[0]
    return {
        str(e.properties["number"]): float(e.properties["area_m2"])
        for e in page.elements
        if e.kind == "room" and e.properties.get("number") and e.properties.get("area_m2")
    }


def _traced(png: Path, settings: Settings) -> dict[str, float | None]:
    page = read_image(png, settings, lambda stage, f: None).pages[0]
    out: dict[str, float | None] = {}
    for e in page.elements:
        number = e.properties.get("number")
        if e.kind == "room" and number:
            measured = (
                e.properties.get("measured_area_m2") if "polygon_px" in e.properties else None
            )
            out[str(number)] = float(measured) if measured is not None else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="the dataset's swiss_dwellings folder")
    parser.add_argument("--limit", type=int, default=8, help="floors to score (default 8)")
    args = parser.parse_args()
    settings = Settings.model_construct(vision_url=None)  # no database needed
    total = FloorScore(0, 0, 0, 0)
    for png in sorted(args.folder.glob("*.png"))[: args.limit]:
        started = time.monotonic()
        s = score_floor(_truth(png.with_suffix(".dxf"), settings), _traced(png, settings))
        total = total + s
        print(f"{png.stem:32s} rooms {s.rooms:3d}  named {s.named:3d}  outlined {s.outlined:3d}"
              f"  area±5% {s.area_ok:3d}  ({time.monotonic() - started:.0f}s)")  # fmt: skip
    n = max(total.rooms, 1)
    print(f"{'TOTAL':32s} rooms {total.rooms:3d}  named {total.named / n:.0%}  "
          f"outlined {total.outlined / n:.0%}  area±5% {total.area_ok / n:.0%}")  # fmt: skip


if __name__ == "__main__":
    main()
