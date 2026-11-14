"""The video plan: settings plus segments, parsed from video.yaml. Pure, no I/O."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SEGMENT_FIELDS = ("id", "title", "target_s", "on_screen", "voiceover")
SETTING_FIELDS = ("target_s", "max_final_s", "hard_limit_s", "words_per_s")


class PlanError(ValueError):
    """video.yaml is malformed or the plan can't fit the limits."""


@dataclass(frozen=True)
class Settings:
    target_s: float
    max_final_s: float
    hard_limit_s: float
    words_per_s: float


@dataclass(frozen=True)
class Segment:
    id: str
    title: str
    target_s: float
    on_screen: str
    voiceover: str


@dataclass(frozen=True)
class Plan:
    settings: Settings
    segments: tuple[Segment, ...]


@dataclass(frozen=True)
class SegmentBudget:
    id: str
    target_s: float
    words: int
    max_words: int
    est_s: float

    @property
    def over(self) -> bool:
        return self.words > self.max_words


@dataclass(frozen=True)
class PlanReport:
    rows: tuple[SegmentBudget, ...]
    total_target_s: float
    total_est_s: float

    @property
    def fits(self) -> bool:
        return not any(row.over for row in self.rows)


def word_count(text: str) -> int:
    return len(text.split())


def segment_budget(segment: Segment, words_per_s: float) -> SegmentBudget:
    words = word_count(segment.voiceover)
    return SegmentBudget(
        id=segment.id,
        target_s=segment.target_s,
        words=words,
        max_words=math.floor(segment.target_s * words_per_s),
        est_s=words / words_per_s,
    )


def plan_report(plan: Plan) -> PlanReport:
    rows = tuple(segment_budget(s, plan.settings.words_per_s) for s in plan.segments)
    return PlanReport(
        rows=rows,
        total_target_s=sum(r.target_s for r in rows),
        total_est_s=sum(r.est_s for r in rows),
    )


def parse_plan(data: Mapping[str, Any]) -> Plan:
    settings = _parse_settings(_require_mapping(data, "settings"))
    raw_segments = data.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise PlanError("segments: must be a non-empty list")
    segments = tuple(_parse_segment(i, raw) for i, raw in enumerate(raw_segments))

    ids = [s.id for s in segments]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise PlanError(f"segments: duplicate id(s) {', '.join(duplicates)}")

    total = sum(s.target_s for s in segments)
    if total > settings.target_s:
        raise PlanError(
            f"segments: target_s adds up to {total:g} s, more than the {settings.target_s:g} s target"
        )
    return Plan(settings=settings, segments=segments)


def _require_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise PlanError(f"{key}: missing or not a mapping")
    return value


def _number(raw: Mapping[str, Any], key: str, where: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PlanError(f"{where}.{key}: missing or not a number")
    if value <= 0:
        raise PlanError(f"{where}.{key}: must be positive, got {value}")
    return float(value)


def _parse_settings(raw: Mapping[str, Any]) -> Settings:
    values = {key: _number(raw, key, "settings") for key in SETTING_FIELDS}
    settings = Settings(**values)
    if not settings.target_s <= settings.max_final_s <= settings.hard_limit_s:
        raise PlanError(
            "settings: need target_s <= max_final_s <= hard_limit_s, got "
            f"{settings.target_s:g} / {settings.max_final_s:g} / {settings.hard_limit_s:g}"
        )
    return settings


def _parse_segment(index: int, raw: object) -> Segment:
    where = f"segments[{index}]"
    if not isinstance(raw, Mapping):
        raise PlanError(f"{where}: not a mapping")
    for key in SEGMENT_FIELDS:
        if key not in raw:
            raise PlanError(f"{where}.{key}: missing")
    texts = {}
    for key in ("id", "title", "on_screen", "voiceover"):
        value = raw[key]
        if not isinstance(value, str):
            raise PlanError(f"{where}.{key}: must be text")
        texts[key] = value.strip()
    if not texts["id"]:
        raise PlanError(f"{where}.id: empty")
    return Segment(target_s=_number(raw, "target_s", where), **texts)
