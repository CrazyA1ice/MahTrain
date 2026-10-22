"""Shared UTC rolling windows for all local graded history dashboards."""
from datetime import datetime, timedelta, timezone

WINDOW_DAYS={"all":None,"year":365,"month":30,"week":7}

def history_since(period: str) -> str | None:
    if type(period) is not str or period not in WINDOW_DAYS:
        raise ValueError("period must be all, year, month or week")
    days=WINDOW_DAYS[period]
    return ((datetime.now(timezone.utc)-timedelta(days=days))
            .isoformat(timespec="seconds") if days is not None else None)
