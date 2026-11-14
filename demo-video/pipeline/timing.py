"""Duration verdict for the final video. Pure."""

from enum import Enum


class Verdict(Enum):
    OK = "ok"  # at or under the target
    WARN = "warn"  # over the target but within the allowed maximum
    FAIL = "fail"  # over the allowed maximum: do not upload


def duration_verdict(duration_s: float, target_s: float, max_final_s: float) -> Verdict:
    if duration_s > max_final_s:
        return Verdict.FAIL
    if duration_s > target_s:
        return Verdict.WARN
    return Verdict.OK
