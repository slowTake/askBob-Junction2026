"""Cache keys for voice clips, so only changed segments are regenerated (and paid for). Pure."""

import hashlib
import json


def clip_key(text: str, voice_id: str, model_id: str) -> str:
    normalized = " ".join(text.split())
    payload = json.dumps([normalized, voice_id, model_id], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def clip_filename(index: int, segment_id: str, key: str) -> str:
    return f"{index:02d}-{segment_id}-{key}.mp3"
