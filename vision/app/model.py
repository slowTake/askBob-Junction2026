"""The CubiCasa5k network: load it and run it over a page in tiles.

CubiCasa5k's code is cloned into CUBICASA_DIR when the image is built (D-022), not
vendored: it is CC BY-NC 4.0 and its post-processing file is over our size limit.
"""

import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from app.tiles import edge_weights, keep_windows, tile_starts

CUBICASA_DIR = Path(os.environ.get("CUBICASA_DIR", "/opt/cubicasa"))
sys.path.insert(0, str(CUBICASA_DIR))

CHANNELS = 44
SPLIT = [21, 12, 11]  # corner heatmaps, room classes, object classes
TILE = 1024
OVERLAP = 128
# (turn before, turn back) pairs, as in CubiCasa's notebook; the first is "no rotation".
ROTATIONS = [(0, 0), (1, -1), (2, 2), (-1, 1)]


class FloorplanModel:
    def __init__(self, weights: Path, rotations: int = 1, device: str = "cpu") -> None:
        from floortrans.loaders.augmentations import RotateNTurns
        from floortrans.models.hg_furukawa_original import hg_furukawa_original

        # get_model() would also load a pose-model init we don't ship; the checkpoint
        # replaces every weight anyway.
        net = hg_furukawa_original(n_classes=51)
        net.conv4_ = torch.nn.Conv2d(256, CHANNELS, bias=True, kernel_size=1)
        net.upsample = torch.nn.ConvTranspose2d(CHANNELS, CHANNELS, kernel_size=4, stride=4)
        state = torch.load(weights, map_location="cpu", weights_only=False)
        net.load_state_dict(state.get("model_state", state))
        self.device = torch.device(device)
        self.net = net.to(self.device).eval()
        self.rotate = RotateNTurns()
        self.rotations = ROTATIONS[: max(1, min(rotations, len(ROTATIONS)))]

    @torch.no_grad()
    def predict(self, rgb: np.ndarray) -> torch.Tensor:
        """[1, 44, H, W] for an RGB page; overlapping tiles blended by edge weights.

        Full precision: fp16 output tripped an IndexError in CubiCasa's door
        post-processing (D-022).
        """
        h, w = rgb.shape[:2]
        acc = torch.zeros(CHANNELS, h, w)
        weight = torch.zeros(1, h, w)
        for y in tile_starts(h, TILE, OVERLAP):
            for x in tile_starts(w, TILE, OVERLAP):
                part = rgb[y : y + TILE, x : x + TILE]
                th, tw = part.shape[:2]
                wy = torch.from_numpy(edge_weights(th, OVERLAP)).float()
                wx = torch.from_numpy(edge_weights(tw, OVERLAP)).float()
                wgt = (wy[:, None] * wx[None, :])[None]
                acc[:, y : y + th, x : x + tw] += self._tile(part).cpu() * wgt
                weight[:, y : y + th, x : x + tw] += wgt
        return (acc / weight)[None]

    @torch.no_grad()
    def predict_labels(self, rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(room class, object class) per pixel, as uint8 maps.

        Memory stays bounded by the tile size: each tile's 44 channels are reduced to
        two labels at once, and each pixel comes from the one tile that owns it
        (keep_windows), so no page-sized float map is ever built (D-023).
        """
        h, w = rgb.shape[:2]
        rooms = np.zeros((h, w), np.uint8)
        icons = np.zeros((h, w), np.uint8)
        ys, xs = tile_starts(h, TILE, OVERLAP), tile_starts(w, TILE, OVERLAP)
        for y, (ya, yb) in zip(ys, keep_windows(ys, TILE, h), strict=True):
            for x, (xa, xb) in zip(xs, keep_windows(xs, TILE, w), strict=True):
                out = self._tile(rgb[y : y + TILE, x : x + TILE])[:, ya:yb, xa:xb]
                # argmax on the device, so only two small label maps cross to the CPU.
                room_part = out[SPLIT[0] : SPLIT[0] + SPLIT[1]].argmax(0).cpu()
                icon_part = out[SPLIT[0] + SPLIT[1] :].argmax(0).cpu()
                rooms[y + ya : y + yb, x + xa : x + xb] = room_part.numpy().astype(np.uint8)
                icons[y + ya : y + yb, x + xa : x + xb] = icon_part.numpy().astype(np.uint8)
        return rooms, icons

    def _tile(self, rgb: np.ndarray) -> torch.Tensor:
        """[44, h, w] for one tile, on the model's device."""
        h, w = rgb.shape[:2]
        x = torch.from_numpy(np.moveaxis(rgb, -1, 0).copy()).float()[None].to(self.device)
        x = 2 * (x / 255.0) - 1  # the normalisation CubiCasa trained with
        total = torch.zeros(CHANNELS, h, w, device=self.device)
        for turn, back in self.rotations:
            out: Any = self.net(self.rotate(x, "tensor", turn))
            out = self.rotate(self.rotate(out, "tensor", back), "points", back)
            total += F.interpolate(out, size=(h, w), mode="bilinear", align_corners=True)[0]
        return total / len(self.rotations)
