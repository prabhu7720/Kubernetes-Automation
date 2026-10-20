"""Window/cron helpers for scheduled searches."""

from __future__ import annotations

from core.models import WINDOW_RE


def parse_window(window: str) -> tuple[int, str]:
    m = WINDOW_RE.match(window)
    if not m:
        raise ValueError(f"Invalid window {window!r}")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "s":
        n, unit = max(1, n // 60), "m"
    return max(1, n), unit


def window_seconds(window: str) -> int:
    n, unit = parse_window(window)
    return n * {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]


def window_schedule(window: str) -> tuple[str, str, str]:
    """Return (cron, earliest, latest) so each run evaluates exactly one closed window."""
    n, unit = parse_window(window)
    if unit == "m":
        cron = "* * * * *" if n == 1 else f"*/{n} * * * *"
        return cron, f"-{n}m@m", "@m"
    if unit == "h":
        cron = "0 * * * *" if n == 1 else f"0 */{n} * * *"
        return cron, f"-{n}h@h", "@h"
    if unit == "d":
        cron = "15 0 * * *" if n == 1 else f"15 0 */{n} * *"
        return cron, f"-{n}d@d", "@d"
    return "30 0 * * 1", f"-{n}w@w1", "@w1"


def describe_cron(cron: str) -> str:
    parts = cron.split()
    if len(parts) != 5:
        return cron
    minute, hour, dom, month, dow = parts
    if cron == "* * * * *":
        return "every minute"
    if minute.startswith("*/") and hour == "*":
        return f"every {minute[2:]} minutes"
    if hour == "*" and minute.isdigit():
        return f"hourly at :{int(minute):02d}"
    if hour.startswith("*/") and minute.isdigit():
        return f"every {hour[2:]} hours"
    if minute.isdigit() and hour.isdigit():
        at = f"{int(hour):02d}:{int(minute):02d}"
        if dom == "*" and dow == "*":
            return f"daily at {at}"
        if dom == "*" and dow.isdigit():
            day = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][int(dow) % 7]
            return f"weekly on {day} at {at}"
        if dom.isdigit():
            return f"monthly on day {dom} at {at}"
    return cron
