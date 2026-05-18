import json
import threading
import time
from pathlib import Path

_MEMORY_DIR = Path(__file__).resolve().parent.parent / "data"
_MEMORY_FILE = _MEMORY_DIR / "guardian_memory.json"
_LOCK = threading.Lock()
_MAX_COMMANDS = 200
_MAX_ROUTINES = 50


def _load() -> dict:
    if not _MEMORY_FILE.exists():
        return {"users": {}}
    try:
        return json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"users": {}}


def _save(data: dict) -> None:
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _user_key(user_id: int | None, user_name: str | None) -> str:
    if user_id is not None:
        return f"id:{user_id}"
    if user_name and user_name.strip():
        return f"name:{user_name.strip().lower()}"
    return "anonymous"


def record_command(user_id: int | None, user_name: str | None, text: str, intent: str) -> None:
    key = _user_key(user_id, user_name)
    entry = {
        "text": text.strip()[:300],
        "intent": intent,
        "ts": time.time(),
    }
    with _LOCK:
        data = _load()
        users = data.setdefault("users", {})
        profile = users.setdefault(key, {"commands": [], "preferences": {}, "routines": []})
        cmds = profile.setdefault("commands", [])
        cmds.insert(0, entry)
        profile["commands"] = cmds[:_MAX_COMMANDS]
        _save(data)


def get_frequent_commands(user_id: int | None, user_name: str | None, limit: int = 5) -> list[str]:
    key = _user_key(user_id, user_name)
    with _LOCK:
        data = _load()
        profile = data.get("users", {}).get(key, {})
        cmds = profile.get("commands", [])

    counts: dict[str, int] = {}
    for c in cmds:
        t = c.get("text", "").strip().lower()
        if t:
            counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [text for text, _ in ranked[:limit]]


def set_preference(user_id: int | None, user_name: str | None, key: str, value: str) -> None:
    ukey = _user_key(user_id, user_name)
    with _LOCK:
        data = _load()
        users = data.setdefault("users", {})
        profile = users.setdefault(ukey, {"commands": [], "preferences": {}, "routines": []})
        profile.setdefault("preferences", {})[key] = value
        _save(data)


def get_preferences(user_id: int | None, user_name: str | None) -> dict[str, str]:
    key = _user_key(user_id, user_name)
    with _LOCK:
        data = _load()
        profile = data.get("users", {}).get(key, {})
        return dict(profile.get("preferences", {}))


def memory_entry_count() -> int:
    with _LOCK:
        data = _load()
        return sum(
            len(p.get("commands", [])) + len(p.get("preferences", {}))
            for p in data.get("users", {}).values()
        )
