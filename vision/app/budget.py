"""How big the network's input may get, whatever the upload (D-023).

Memory and time grow with the pixels the network sees, so the scale is the
drawing's desired zoom capped by a pixel budget: small drawings are enlarged,
huge sheets are shrunk. Only small inputs take CubiCasa's detailed polygon step,
which needs all 44 output channels for the whole page.
"""

import math
from dataclasses import dataclass

MIN_SCALE = 0.35  # below this, walls are a pixel thick and the model sees nothing


@dataclass(frozen=True)
class Plan:
    scale: float
    detailed: bool  # all 44 channels + CubiCasa's polygons, vs. class labels only


def plan_for(
    width: int, height: int, desired: float, budget_px: float, detailed_px: float
) -> Plan | None:
    """None: too dense to read within the budget (or nothing to read)."""
    area = width * height
    if area <= 0:
        return None
    scale = min(desired, math.sqrt(budget_px / area))
    if scale < MIN_SCALE:
        return None
    return Plan(scale=scale, detailed=area * scale * scale <= detailed_px)
