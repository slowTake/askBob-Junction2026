"""Ask the `vision` service (D-022) to read a page image. Never raises into a reader.

Returns the parsed result and a status for the page's metadata:
- "used": the service answered;
- "unavailable": not configured, or nothing is listening;
- "failed": it answered with an error, garbage, or took too long;
- "skipped": the page is too large or dense to read within its budget (D-023).
"""

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Literal

from app.config import Settings
from app.domain.vision import Parsed, parse

log = logging.getLogger(__name__)
Status = Literal["used", "unavailable", "failed", "skipped"]


def analyse_page(png: bytes, settings: Settings) -> tuple[Parsed | None, Status]:
    if not settings.vision_url:
        return None, "unavailable"
    request = urllib.request.Request(
        settings.vision_url.rstrip("/") + "/analyse",
        data=png,
        headers={"Content-Type": "image/png"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.vision_timeout_s) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError:
        log.warning("vision service answered with an error status", exc_info=True)
        return None, "failed"
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError | socket.timeout):
            log.warning("vision service timed out")
            return None, "failed"
        log.info("vision service unavailable: %s", exc.reason)
        return None, "unavailable"
    except TimeoutError:
        log.warning("vision service timed out")
        return None, "failed"
    except (OSError, ValueError):
        log.warning("vision service answer unreadable", exc_info=True)
        return None, "failed"
    if not isinstance(body, dict) or body.get("ok") is not True:
        log.warning("vision service could not read the page")
        return None, "failed"
    data = body.get("data")
    if isinstance(data, dict) and data.get("method") == "skipped_too_large":
        return None, "skipped"
    return parse(data), "used"
