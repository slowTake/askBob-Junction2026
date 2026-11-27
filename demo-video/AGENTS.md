# Instructions for AI agents in `demo-video/`

This directory builds the **2-minute Junction demo video** for askBob. It is **not part of the app**: nothing in `backend/` or `frontend/` imports it, and it ships nothing to users. Read this file before touching anything here; read [README.md](README.md) for the commands.

## What's different from the rest of the repo

Per [D-011](../docs/decisions.md):

- **No tests and no CI for this directory.** Don't add `*_test.py` files, don't add it to the root `make check`, and don't add a CI job for it. RULES.md §3 (tested logic) and §8 (CI) don't apply here.
- It is its own uv project (`pyproject.toml`, `uv.lock`). Don't add its dependencies to `backend/`, and don't import app code from here.

These repo rules **still apply**:

- Conventional commits (`feat(demo-video): …`), no `--no-verify`, PRs to `main`, an issue per chunk of work (see the root [AGENTS.md](../AGENTS.md) and [CLAUDE.md](../CLAUDE.md)).
- No source file over 600 lines; the repo-wide size check covers this directory.
- **No secrets anywhere** (RULES.md §6, D-009). API keys live in the OS keyring. `pipeline/keys.py` fetches them when a step needs them. Never print, log, echo or write a key, and never ask for one in chat. `make keys` checks they're found without showing them.
- Log decisions in `docs/decisions.md`.

If you need to change the app itself (for example to add `data-testid` hooks for the recordings), that's app work: a separate issue and PR under the normal rules, not part of a `demo-video` change.

## Rules for the video itself

These come from Junction's rules and the Stoa judging criteria. Don't trade them away for convenience.

1. **Length:** Junction's rule is "not a second longer than 2 minutes", title cards included. The target is 110 s, and `make check` must pass (≤ 115 s) before anything is uploaded.
2. **Real footage only.** Every product shot is a real recording of the real app answering a real question. Never generate, mock or edit an answer. The judges score how verifiable the answers are.
3. **Generated media is voice only** (ElevenLabs). No background music, no AI-generated images or b-roll. Gemini reviews the cut; it doesn't make footage.
4. **Show the low-confidence case honestly** (the phone photo segment).
5. **`video.yaml` is the single source of truth** for segments, voiceover text and limits. Change text there, then run `make plan`. Don't hardcode script text anywhere else.

## Spending money and asking first

- `make voice` spends ElevenLabs credits, but only on segments whose text changed (clips are cached by text, voice and model). Don't delete `out/audio/` or change the voice or model without a reason; that regenerates every clip.
- **The voice (Daniel, `eleven_v4`) was approved by Peter.** Changing `voice.voice_id`, `voice.model_id` or `voice.approved` needs his approval first; use `make voice-test` to produce a sample.
- Every take of a new question costs one Claude call in the app (repeats come from the app's answer cache).
- **Uploading the video publishes it.** Prepare everything, then ask the team before uploading.

## Status (update when a step changes)

| Step | Status |
|---|---|
| `keys`, `plan`, `check` | work |
| `voices`, `voice-test`, `voice` | work; all 7 clips generated with Daniel |
| `captions` | works |
| `record` | stub: needs the 3 frozen demo questions, the demo files loaded in the app (including a real phone photo of the printed sheet), and `data-testid` hooks in the frontend |
| `assemble` | stub |
| `review` | stub (Gemini key is in place) |

The `close` segment's voiceover has `X of Y` placeholders until `backend/eval` produces real numbers.

## Media

Everything generated goes in `out/`, which is git-ignored. Never commit audio, video or recordings. The finished video goes to YouTube or Vimeo.
