from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .jobs import run_daily_jobs


@dataclass(frozen=True)
class ScheduledWindow:
    name: str
    hour: int
    minute: int


WINDOWS = [
    ScheduledWindow(name="pre_market", hour=9, minute=0),
    ScheduledWindow(name="post_close", hour=16, minute=0),
]


def next_windows(now: datetime | None = None, tz: str = "Asia/Shanghai") -> list[datetime]:
    now = now or datetime.now(ZoneInfo(tz))
    out: list[datetime] = []
    for win in WINDOWS:
        candidate = now.replace(hour=win.hour, minute=win.minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        out.append(candidate)
    return sorted(out)


def run_once() -> dict[str, str | int]:
    return run_daily_jobs()
