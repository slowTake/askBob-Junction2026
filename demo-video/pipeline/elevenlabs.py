"""Minimal ElevenLabs client (stdlib only). Checked against the API docs on 2026-11-14:

- POST /v1/text-to-speech/{voice_id}?output_format=...  body {text, model_id}  -> audio bytes
- GET  /v2/voices?page_size=...&search=...                                  -> {voices: [...]}
Auth header: xi-api-key.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API = "https://api.elevenlabs.io"


class ElevenLabsError(RuntimeError):
    """The API answered with an error. The message never contains the key."""


@dataclass(frozen=True)
class Voice:
    voice_id: str
    name: str
    category: str
    labels: dict[str, str]


def _request(req: urllib.request.Request) -> bytes:
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return bytes(resp.read())
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:300]
        hint = ""
        if err.code in (401, 403):
            hint = " (key missing this permission, expired, or wrong; check its endpoint access)"
        raise ElevenLabsError(f"HTTP {err.code}{hint}: {detail}") from None
    except urllib.error.URLError as err:
        raise ElevenLabsError(f"network error: {err.reason}") from None


def list_voices(key: str, search: str = "", page_size: int = 100) -> list[Voice]:
    query = urllib.parse.urlencode({"page_size": page_size, "search": search} if search else {"page_size": page_size})
    req = urllib.request.Request(f"{API}/v2/voices?{query}", headers={"xi-api-key": key})
    data = json.loads(_request(req))
    return [
        Voice(
            voice_id=v["voice_id"],
            name=v.get("name", ""),
            category=v.get("category", ""),
            labels={k: str(val) for k, val in (v.get("labels") or {}).items()},
        )
        for v in data.get("voices", [])
    ]


def synthesize(
    key: str, voice_id: str, model_id: str, text: str, output_format: str, target: Path
) -> None:
    query = urllib.parse.urlencode({"output_format": output_format})
    body = json.dumps({"text": text, "model_id": model_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/v1/text-to-speech/{urllib.parse.quote(voice_id)}?{query}",
        data=body,
        method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    audio = _request(req)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")
    tmp.write_bytes(audio)
    tmp.replace(target)  # never leave a half-written clip under its cache name
