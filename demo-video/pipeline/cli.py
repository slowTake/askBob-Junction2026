"""Command line for the demo video pipeline. All I/O lives here; logic is in the sibling modules.

Run from demo-video/: `uv run python -m pipeline.cli <step>`, or use the Makefile.
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

from pipeline.cache import clip_filename, clip_key
from pipeline.captions import cues_for_segment, to_srt
from pipeline.plan import Plan, PlanError, parse_plan, plan_report
from pipeline.timing import Verdict, duration_verdict

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

NOT_YET = {
    "voice": "ElevenLabs clip per segment into out/audio/ (handoff phase 2)",
    "record": "Playwright take per segment into out/recordings/ (handoff phase 3)",
    "assemble": "ffmpeg: recordings + audio + captions -> out/final.mp4 (handoff phase 4)",
    "review": "Gemini critique of out/final.mp4 against checklist.md (handoff phase 5)",
}


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
    voice = settings.get("voice", {})
    voice_id, model_id = voice.get("voice_id", ""), voice.get("model_id", "")
    cues, start = [], 0.0
    for index, seg in enumerate(plan.segments, start=1):
        clip = OUT / "audio" / clip_filename(index, seg.id, clip_key(seg.voiceover, voice_id, model_id))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    parser.add_argument("--plan", type=Path, default=ROOT / "video.yaml")
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("plan", help="word budget per segment; fails if the script can't fit")
    check = sub.add_parser("check", help="ffprobe the final video; fails if too long")
    check.add_argument("video", type=Path, nargs="?", default=OUT / "final.mp4")
    sub.add_parser("captions", help="out/captions.srt from voiceover text + clip lengths")
    for name, what in NOT_YET.items():
        sub.add_parser(name, help=f"not implemented yet: {what}")
    args = parser.parse_args(argv)

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
    print(f"not implemented yet: {NOT_YET[args.step]}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
