"""Which uploaded files describe the same drawing."""

from dataclasses import dataclass
from pathlib import PurePath


def drawing_stem(filename: str) -> str:
    return PurePath(filename.replace("\\", "/")).stem.casefold()


def companion_matches(image_filename: str, cad_filename: str) -> bool:
    return bool(drawing_stem(image_filename)) and drawing_stem(image_filename) == drawing_stem(
        cad_filename
    )


@dataclass(frozen=True)
class Candidate:
    id: str
    filename: str
    sha256: str
    status: str


def matching_id(filename: str, candidates: list[Candidate]) -> str | None:
    matching = [
        c for c in candidates if c.status != "failed" and companion_matches(filename, c.filename)
    ]
    if not matching or len({c.sha256 for c in matching}) != 1:
        return None
    return min(c.id for c in matching)
