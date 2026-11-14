"""Command line for the demo video pipeline. All I/O lives here; logic is in the sibling modules.

Run from demo-video/: `uv run python -m pipeline.cli <step>`, or use the Makefile.
"""

import argparse
from collections.abc import Callable
import subprocess
import sys
from pathlib import Path

import yaml

from pipeline.captions import cues_for_segment, to_srt
from pipeline.elevenlabs import ElevenLabsError
from pipeline.keys import ENV_VAR, KeyMissing, get_key, key_source, store_hint
from pipeline.plan import Plan, PlanError, parse_plan, plan_report
from pipeline.timing import Verdict, duration_verdict
from pipeline.voice import clip_path, cmd_voice, cmd_voice_test, cmd_voices, voice_settings

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

NOT_YET = {
    "record": "Playwright take per segment into out/recordings/ (handoff phase 3)",
    "assemble": "ffmpeg: recordings + audio + captions -> out/final.mp4 (handoff phase 4)",
    "review": "Gemini critique of out/final.mp4 against checklist.md (handoff phase 5)",
}
# Steps that call an API fetch their key first, so a missing key fails before any work.
NEEDS_KEY = {
    "voices": "elevenlabs",
    "voice-test": "elevenlabs",
    "voice": "elevenlabs",
    "review": "gemini",
}


def cmd_keys() -> int:
    missing = 0
    for service, env_var in ENV_VAR.items():
        source = key_source(service)
        if source is None:
            missing += 1
            print(f"{service:<11} MISSING  store it once with: {store_hint(service)}")
        else:
            print(f"{service:<11} found ({'$' + env_var if source == 'env' else 'OS keyring'})")
    return 1 if missing else 0


def load_plan(path: Path) -> tuple[Plan, dict]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parse_plan(raw), raw.get("settings", {})


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def cmd_plan(plan: Plan) -> int:
    report = plan_report(plan)
    print(f"{'segment':<12}{'target s':>9}{'words':>7}{'max':>5}{'est s':>7}")
    for row in report.rows:
        flag = "  OVER" if row.over else ""
        print(f"{row.id:<12}{row.target_s:>9g}{row.words:>7}{row.max_words:>5}{row.est_s:>7.1f}{flag}")
    s = plan.settings
    print(f"\ntimeline {report.total_target_s:g} s (target {s.target_s:g}, Junction max {s.hard_limit_s:g})")
    print(f"voiceover estimate {report.total_est_s:.1f} s at {s.words_per_s:g} words/s")
    if not report.fits:
        print("FAIL: shorten the segments marked OVER")
        return 1
    print("OK: script fits")
    return 0


def cmd_check(plan: Plan, video: Path) -> int:
    if not video.exists():
        print(f"FAIL: {video} not found; build it first")
        return 1
    seconds = probe_duration(video)
    s = plan.settings
    verdict = duration_verdict(seconds, s.target_s, s.max_final_s)
    print(f"{video.name}: {seconds:.2f} s (target {s.target_s:g}, fail above {s.max_final_s:g})")
    if verdict is Verdict.FAIL:
        print(f"FAIL: too long. Junction's limit is {s.hard_limit_s:g} s, title cards included.")
        return 1
    print("WARN: over target, still within limit" if verdict is Verdict.WARN else "OK")
    return 0


def cmd_captions(plan: Plan, settings: dict) -> int:
    vs = voice_settings(settings)
    cues, start = [], 0.0
    for index, seg in enumerate(plan.segments, start=1):
        clip = clip_path(OUT / "audio", index, seg, vs)
        if not clip.exists():
            print(f"FAIL: missing voice clip {clip.name}; run `make voice` first")
            return 1
        cues += cues_for_segment(seg.voiceover, start, probe_duration(clip))
        start += seg.target_s
    target = OUT / "captions.srt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_srt(cues), encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)} ({len(cues)} cues)")
    return 0


def _api(step: Callable[[], int]) -> int:
    try:
        return step()
    except ElevenLabsError as err:
        print(f"FAIL: ElevenLabs {err}")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    parser.add_argument("--plan", type=Path, default=ROOT / "video.yaml")
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("plan", help="word budget per segment; fails if the script can't fit")
    check = sub.add_parser("check", help="ffprobe the final video; fails if too long")
    check.add_argument("video", type=Path, nargs="?", default=OUT / "final.mp4")
    sub.add_parser("captions", help="out/captions.srt from voiceover text + clip lengths")
    sub.add_parser("keys", help="check the API keys can be found (never prints them)")
    voices = sub.add_parser("voices", help="list ElevenLabs voices to pick from")
    voices.add_argument("--search", default="")
    test = sub.add_parser("voice-test", help="generate only the first segment's clip")
    test.add_argument("--voice", default="", help="voice_id to try (overrides video.yaml)")
    sub.add_parser("voice", help="all clips; needs voice.approved: true in video.yaml")
    for name, what in NOT_YET.items():
        sub.add_parser(name, help=f"not implemented yet: {what}")
    args = parser.parse_args(argv)

    if args.step == "keys":
        return cmd_keys()
    key = ""
    if args.step in NEEDS_KEY:
        try:
            key = get_key(NEEDS_KEY[args.step])
        except KeyMissing as err:
            print(f"FAIL: {err}")
            return 1
    if args.step == "voices":
        return _api(lambda: cmd_voices(key, args.search))

    try:
        plan, settings = load_plan(args.plan)
    except PlanError as err:
        print(f"FAIL: {args.plan.name}: {err}")
        return 1

    if args.step == "plan":
        return cmd_plan(plan)
    if args.step == "check":
        return cmd_check(plan, args.video)
    if args.step == "captions":
        return cmd_captions(plan, settings)
    audio = OUT / "audio"
    if args.step == "voice-test":
        vs = voice_settings(settings, args.voice)
        return _api(lambda: cmd_voice_test(key, plan, vs, audio, probe_duration))
    if args.step == "voice":
        vs = voice_settings(settings)
        return _api(lambda: cmd_voice(key, plan, vs, audio, probe_duration))
    print(f"not implemented yet: {NOT_YET[args.step]}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
