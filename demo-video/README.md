# Demo video pipeline

Builds the 2-minute Junction demo video from one file, [`video.yaml`](video.yaml). Edit the text there, run `make`, and the voice, captions and length check follow.

This directory is **separate from the app**: it is not part of `make check`, CI or the test suite (see D-011 in [docs/decisions.md](../docs/decisions.md)).

## The rule we build around

Junction: the video must be "not a second longer than 2 minutes", enforced strictly. We count everything in the file, title cards included. We aim for **110 s**, and `make check` **fails above 115 s**.

## Prerequisites

- [uv](https://docs.astral.sh/uv/), `ffmpeg` and `ffprobe` on your PATH
- For the voice and review steps, API keys in your **OS keyring** (D-009: never in a file, `.env` or chat):
  - Linux: `secret-tool store --label="ElevenLabs" service elevenlabs`, and the same with `service gemini`
  - macOS: `security add-generic-password -s elevenlabs -a "$USER" -w`, and the same with `-s gemini`

  That's all: the steps that call an API (`voice`, `review`) fetch their key from the keyring themselves, only for that run, and never print or save it. `make keys` checks that both keys can be found. A `GEMINI_API_KEY` or `ELEVENLABS_API_KEY` already set in the environment takes precedence.

## Steps

| Command | What it does | Status |
|---|---|---|
| `make keys` | Checks the Gemini and ElevenLabs keys can be found; never prints them | works |
| `make plan` | Word budget per segment at 2.3 words/s; fails if any segment is over | works |
| `make voice` | One ElevenLabs clip per segment in `out/audio/`; only changed text is regenerated | stub |
| `make record` | One scripted Playwright take per segment in `out/recordings/` | stub |
| `make captions` | `out/captions.srt` from the voiceover text and measured clip lengths | works once clips exist |
| `make assemble` | ffmpeg joins recordings, audio and burned-in captions into `out/final.mp4` | stub |
| `make review` | Gemini critiques `out/final.mp4` against [checklist.md](checklist.md) | stub |
| `make check` | `ffprobe` on `out/final.mp4`; fails above 115 s | works |

`out/` is git-ignored. Media never goes in the repo; the final video goes to YouTube or Vimeo.

## Rules for whoever builds the video (people and agents)

- Every product shot is a real recording of the real app. Never generate or mock product footage.
- No background music and no AI-generated b-roll.
- Check the current ElevenLabs and Gemini API docs before implementing a stub; don't rely on remembered endpoints or model names.
- Generate one test voice clip and get it approved before generating the rest.
- Uploading the video publishes it: ask the team first.

## Layout

```
video.yaml        settings + segments (the single source of truth)
checklist.md      final-cut checklist
pipeline/plan.py      parse and validate video.yaml, word budget
pipeline/timing.py    duration verdict (ok / warn / fail)
pipeline/cache.py     voice-clip cache key and file names
pipeline/captions.py  SRT cues from text and clip lengths
pipeline/keys.py      API keys from the environment or the OS keyring, on demand
pipeline/cli.py       the commands above (all I/O lives here)
```
