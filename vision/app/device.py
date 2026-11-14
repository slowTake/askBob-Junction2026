"""Where the network runs: `VISION_DEVICE` = auto (default), cpu or cuda.

auto takes the GPU when the container can see one (the GPU image on a Verda host)
and the CPU otherwise (the local image), so one code path serves both.
"""

CHOICES = ("auto", "cpu", "cuda")


def pick_device(setting: str, cuda_available: bool) -> str:
    choice = setting.strip().lower() or "auto"
    if choice not in CHOICES:
        raise ValueError(f"VISION_DEVICE must be one of {', '.join(CHOICES)}")
    if choice == "cuda" and not cuda_available:
        raise ValueError("VISION_DEVICE=cuda but no GPU is visible to the container")
    if choice == "auto":
        return "cuda" if cuda_available else "cpu"
    return choice
