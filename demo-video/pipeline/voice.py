"""The voice steps: list voices, one test clip, then all clips (only changed text is regenerated)."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.cache import clip_filename, clip_key
from pipeline.elevenlabs import list_voices, synthesize
from pipeline.plan import Plan, Segment

Probe = Callable[[Path], float]


@dataclass(frozen=True)
class VoiceSettings:
    voice_id: str
    model_id: str
    output_format: str
    approved: bool


def voice_settings(settings: Mapping[str, Any], voice_override: str = "") -> VoiceSettings:
    raw = settings.get("voice") or {}
    return VoiceSettings(
        voice_id=voice_override or str(raw.get("voice_id") or ""),
        model_id=str(raw.get("model_id") or "eleven_v4"),
        output_format=str(raw.get("output_format") or "mp3_44100_128"),
        approved=bool(raw.get("approved")) and not voice_override,
    )


def clip_path(audio_dir: Path, index: int, seg: Segment, vs: VoiceSettings) -> Path:
    key = clip_key(seg.voiceover, vs.voice_id, vs.model_id)
    return audio_dir / clip_filename(index, seg.id, key)


def cmd_voices(key: str, search: str) -> int:
    voices = list_voices(key, search)
    if not voices:
        print("no voices found")
        return 1
    print(f"{'voice_id':<24}{'name':<22}{'category':<12}labels")
    for v in sorted(voices, key=lambda v: v.name.lower()):
        labels = ", ".join(f"{k}={val}" for k, val in sorted(v.labels.items()))
        print(f"{v.voice_id:<24}{v.name[:21]:<22}{v.category[:11]:<12}{labels}")
    print('\nPick one, then: make voice-test VOICE=<voice_id>')
    return 0


def _make_clip(key: str, path: Path, seg: Segment, vs: VoiceSettings) -> bool:
    """Returns True if a new clip was generated (paid), False if the cached one was reused."""
    if path.exists():
        return False
    synthesize(key, vs.voice_id, vs.model_id, seg.voiceover, vs.output_format, path)
    return True


def cmd_voice_test(key: str, plan: Plan, vs: VoiceSettings, audio_dir: Path, probe: Probe) -> int:
    if not vs.voice_id:
        print("FAIL: no voice chosen. Run `make voices`, then `make voice-test VOICE=<voice_id>`")
        return 1
    seg = plan.segments[0]
    path = clip_path(audio_dir, 1, seg, vs)
    made = _make_clip(key, path, seg, vs)
    seconds = probe(path)
    print(f"{'generated' if made else 'reused'} {path} ({seconds:.1f} s, target {seg.target_s:g} s)")
    print(
        "\nListen to it. If you like the voice, set in video.yaml:\n"
        f"  voice.voice_id: {vs.voice_id}\n  voice.approved: true\n"
        "then run `make voice` for the rest (this clip is reused, not paid again)."
    )
    return 0


def cmd_voice(key: str, plan: Plan, vs: VoiceSettings, audio_dir: Path, probe: Probe) -> int:
    if not vs.voice_id or not vs.approved:
        print("FAIL: voice not approved yet. Run `make voice-test`, listen, then set "
              "voice.voice_id and voice.approved: true in video.yaml")
        return 1
    over = 0
    print(f"{'segment':<12}{'clip':>8}{'target':>8}  status")
    for index, seg in enumerate(plan.segments, start=1):
        path = clip_path(audio_dir, index, seg, vs)
        _remove_stale(audio_dir, index, seg, keep=path)
        made = _make_clip(key, path, seg, vs)
        seconds = probe(path)
        status = "new" if made else "cached"
        if seconds > seg.target_s:
            over += 1
            status += "  OVER: shorten the text"
        print(f"{seg.id:<12}{seconds:>7.1f}s{seg.target_s:>7g}s  {status}")
    if over:
        print(f"\nFAIL: {over} clip(s) longer than their segment")
        return 1
    print("\nOK: all clips fit. Next: make captions")
    return 0


def _remove_stale(audio_dir: Path, index: int, seg: Segment, keep: Path) -> None:
    for old in audio_dir.glob(f"{index:02d}-{seg.id}-*.mp3"):
        if old != keep:
            old.unlink()
