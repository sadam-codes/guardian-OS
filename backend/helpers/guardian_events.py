import time

_recent_events: list[dict] = []
_MAX_RECENT = 100


def push_recent_event(event: dict) -> None:
    event["ts"] = time.time()
    _recent_events.insert(0, event)
    del _recent_events[_MAX_RECENT:]


def list_recent_events(limit: int = 30) -> list[dict]:
    return _recent_events[: min(limit, 50)]
