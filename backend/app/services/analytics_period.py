from datetime import datetime, timedelta, timezone


def reporting_cutoff(days: int) -> datetime:
    """Zero means all stored history, with no rolling-window or retention cap."""
    if days == 0:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=days)
