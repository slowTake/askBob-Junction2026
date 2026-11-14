"""API keys for the pipeline, fetched when a step needs them (D-009: never from a file).

Order: an environment variable if already set, otherwise the OS keyring. The key is held in
memory for this process only and is never printed or written anywhere.
"""

import os
import subprocess
import sys

ENV_VAR = {"gemini": "GEMINI_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY"}


class KeyMissing(RuntimeError):
    """No key in the environment or the keyring."""


def _keyring_command(service: str) -> list[str]:
    if sys.platform == "darwin":
        return ["security", "find-generic-password", "-s", service, "-w"]
    return ["secret-tool", "lookup", "service", service]


def store_hint(service: str) -> str:
    if sys.platform == "darwin":
        return f'security add-generic-password -s {service} -a "$USER" -w'
    return f'secret-tool store --label="{service} API key (Junction)" service {service}'


def key_source(service: str) -> str | None:
    """Where the key would come from ('env' or 'keyring'), or None. Never returns the key."""
    if os.environ.get(ENV_VAR[service], "").strip():
        return "env"
    return "keyring" if _from_keyring(service) else None


def get_key(service: str) -> str:
    value = os.environ.get(ENV_VAR[service], "").strip() or _from_keyring(service)
    if not value:
        raise KeyMissing(f"no {service} key found. Store it once with: {store_hint(service)}")
    return value


def _from_keyring(service: str) -> str:
    try:
        result = subprocess.run(
            _keyring_command(service), capture_output=True, text=True, check=False, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
