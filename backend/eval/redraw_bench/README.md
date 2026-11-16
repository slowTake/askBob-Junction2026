# Redraw benchmark

The drawing the Redrawn view is scored against (#131).

`colorful-34.png` is a scanned two-floor Finnish house plan: yellow rooms, blue sloped-ceiling zones with red `h1600`-style height labels, dark wall bands, decimal-comma dimensions (5,341), handwritten room names, door swings, a spiral and a straight stair, and kitchen and bathroom fixtures. It is 482 × 507 px, so text is 5–8 px tall.

It stays at that size on purpose. The product has to read a floor plan of any quality, so a sharper copy would only hide the problem. There is no higher-resolution original.

## Files

- `colorful-34.truth.json`: the hand-made truth. **Draft**: its `notes` list every entry still to be checked by eye. Check it with an overlay: `uv run python -m eval.redraw_overlay eval/redraw_bench/colorful-34.truth.json /tmp/overlay.png --scale 3` (each element carries its index: w, o, r, t).
- `colorful-34.ocr.json`: the app's OCR words for the page, recorded so the benchmark runs offline.
- `colorful-34.vision.json`: the vision service's answer, or `{"status": "unavailable"}` when none was running.

Run the benchmark with `uv run python -m eval.redraw_bench` (from `backend/`). `--live` runs OCR and the vision service instead of the recordings; `--record` also rewrites them. No paid model is called.

## Truth file format

`colorful-34.truth.json` is read by `eval/redraw_sheet.py:load_sheet`. Coordinates are shares of the page, 0..1 of its width (x) and height (y). A malformed entry is refused, never repaired.

```json
{
  "walls": [
    {"a": [0.10, 0.50], "b": [0.50, 0.50], "thickness": 0.008},
    {"polygon": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.12]]}
  ],
  "openings": [
    {"kind": "door", "a": [0.3, 0.5], "b": [0.33, 0.5], "hinge": "a", "toward": [0.31, 0.53]},
    {"kind": "window", "a": [0.6, 0.0], "b": [0.65, 0.0]}
  ],
  "rooms": [{"name": "keittiö", "label": [0.15, 0.6], "polygon": [[0.07, 0.43], [0.35, 0.43], [0.35, 0.7]]}],
  "texts": [{"text": "5,341", "kind": "dimension", "at": [0.1, 0.17], "rotation": 0}],
  "notes": "anything for the author; ignored"
}
```

- A wall is its centre line with a thickness (a share of the page width), drawn half a thickness past each end so corners close, or its outline.
- A door's `hinge` names the end its leaf turns on; `toward` is any point in the room it opens into.
- A room's `name` is as written; `polygon` may be left out.
- A text's `kind` is `dimension`, `height` or `other` (room names go under rooms); `rotation` is 0 or 90.

## Source and licence

`colorful-34.png` is from CubiCasa5K, unchanged (the file name is the one the Junction dataset preview uses).

Copyright (c) 2019 CubiCasa. Licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): non-commercial use only, and anything derived from it (such as its ground truth) is shared under the same licence.

Credit: Ahti Kalervo, Juha Ylioinas, Markus Häikiö, Antti Karhu, Juho Kannala. "CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image Analysis." SCIA 2019. <https://zenodo.org/records/2613548>
