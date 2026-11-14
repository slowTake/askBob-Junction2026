"""Captions (SRT) from the voiceover text and measured clip lengths. Pure."""

import re
from dataclasses import dataclass

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Cue:
    text: str
    start_s: float
    end_s: float


def format_timestamp(seconds: float) -> str:
    if seconds < 0:
        raise ValueError(f"negative timestamp: {seconds}")
    total_ms = round(seconds * 1000)
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def split_sentences(text: str) -> list[str]:
    return [part for part in _SENTENCE_END.split(text.strip()) if part]


def cues_for_segment(text: str, start_s: float, duration_s: float) -> list[Cue]:
    """One cue per sentence; each sentence gets time in proportion to its word count."""
    sentences = split_sentences(text)
    total_words = sum(len(s.split()) for s in sentences)
    if total_words == 0:
        return []
    per_word = duration_s / total_words
    cues, cursor = [], start_s
    for sentence in sentences:
        end = cursor + len(sentence.split()) * per_word
        cues.append(Cue(sentence, cursor, end))
        cursor = end
    return cues


def to_srt(cues: list[Cue]) -> str:
    blocks = [
        f"{n}\n{format_timestamp(c.start_s)} --> {format_timestamp(c.end_s)}\n{c.text}\n"
        for n, c in enumerate(cues, start=1)
    ]
    return "\n".join(blocks)
