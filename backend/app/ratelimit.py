"""In-memory limits for the public demo, so it can't run up the AI quota. Fine for one server process."""

import datetime as dt
import os
import time

PER_IP = 30  # files
PER_IP_WINDOW_S = 10 * 60
DAILY = int(os.environ.get("DAILY_FILE_LIMIT", "400"))

_hits: dict[str, list[float]] = {}
_day = dt.date.today()
_daily = 0


def check(ip: str) -> str | None:
    """None if allowed, otherwise the reason to show the visitor."""
    global _day, _daily
    today = dt.date.today()
    if today != _day:
        _day, _daily = today, 0
        _hits.clear()
    if _daily >= DAILY:
        return "The demo has reached its daily limit. Please come back tomorrow."
    now = time.monotonic()
    recent = [t for t in _hits.get(ip, []) if now - t < PER_IP_WINDOW_S]
    if len(recent) >= PER_IP:
        return "Too many files in a short time. Please wait a few minutes."
    recent.append(now)
    _hits[ip] = recent
    _daily += 1
    return None
