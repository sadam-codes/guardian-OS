"""Parse 'create folder named X on D drive' — never treat as write_text / .txt file."""

from __future__ import annotations

import re

from schemas.jarvis import JarvisIntent

_FOLDER_REQUEST = re.compile(r"\bcreate\s+(?:a\s+)?folder\b", re.I)
_DRIVE_IN_TEXT = re.compile(
    r"\b(?:on|in|inside|under|from)\s+(?P<letter>[a-z])\s*(?:drive)?\b|\b(?P<path>[a-z]):\s*(?:\\|/)?\b",
    re.I,
)

_CREATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"create\s+(?:a\s+)?folder\s+"
        r"(?:named|called|name(?:d)?\s+as\s+)?"
        r'["\']?(?P<name>[^"\']+?)["\']?'
        r"(?:\s+(?:on|in|inside|under)\s+(?P<parent>.+))?\s*$",
        re.I,
    ),
    re.compile(
        r"create\s+(?:a\s+)?folder\s+"
        r"(?:on|in|inside|under)\s+(?P<parent>.+?)\s+"
        r"(?:named|called|name(?:d)?\s+as\s+)?"
        r'["\']?(?P<name>[^"\']+?)["\']?\s*$',
        re.I,
    ),
    re.compile(
        r"(?:on|in|inside|under)\s+(?P<parent>(?:[a-z]:\s*(?:\\|/)?|[a-z]\s+drive))\s+"
        r".*create\s+(?:a\s+)?folder\s+"
        r"(?:named|called|name(?:d)?\s+as\s+)?"
        r'["\']?(?P<name>[^"\']+?)["\']?\s*$',
        re.I,
    ),
    re.compile(
        r"create\s+(?:a\s+)?folder\s+"
        r'["\']?(?P<name>[\w][\w\s-]*)["\']?\s*$',
        re.I,
    ),
]


def looks_like_create_folder_request(text: str) -> bool:
    return bool(_FOLDER_REQUEST.search(text or ""))


def _clean_folder_name(raw: str) -> str:
    name = " ".join(raw.strip().strip('"\'').split())
    name = re.sub(r"^(?:named|called|name)\s+", "", name, flags=re.I)
    name = re.sub(r"^as\s+", "", name, flags=re.I)
    name = re.sub(r"\s+(?:on|in|inside|under)\s+.+$", "", name, flags=re.I)
    return name.strip()


def _normalize_parent(raw: str | None, full_text: str) -> str | None:
    blob = f"{raw or ''} {full_text}"
    for pat in (_DRIVE_IN_TEXT,):
        m = pat.search(blob)
        if not m:
            continue
        letter = (m.groupdict().get("letter") or m.groupdict().get("path") or "").strip()
        if letter and len(letter) == 1 and letter.isalpha():
            return f"{letter.upper()}:\\"
        path = (m.groupdict().get("path") or "").strip()
        if path and len(path) == 1:
            return f"{path.upper()}:\\"
    if raw:
        p = raw.strip().rstrip("\\/")
        if re.match(r"^[a-z]:$", p, re.I):
            return f"{p.upper()}\\"
        if re.match(r"^[a-z]:\\", p, re.I):
            return p if p.endswith("\\") else p + "\\"
        dm = re.search(r"\b([a-z])\s+drive\b", p, re.I)
        if dm:
            return f"{dm.group(1).upper()}:\\"
    return raw.strip() if raw else None


def parse_create_folder_intent(text: str) -> JarvisIntent | None:
    clean = " ".join((text or "").strip().split())
    if not looks_like_create_folder_request(clean):
        return None

    name: str | None = None
    parent: str | None = None
    for pat in _CREATE_PATTERNS:
        m = pat.search(clean)
        if not m:
            continue
        name = _clean_folder_name(m.group("name") or "")
        parent = _normalize_parent(m.groupdict().get("parent"), clean)
        break

    if not name:
        m = re.search(
            r"create\s+(?:a\s+)?folder\s+(?:named|called|name(?:d)?\s+as\s+)?(.+)$",
            clean,
            re.I,
        )
        if m:
            name = _clean_folder_name(m.group(1))

    if not name:
        return None

    parent = parent or _normalize_parent(None, clean)
    slots: dict[str, str] = {"name": name, "user_text": clean}
    if parent:
        slots["parent"] = parent
    return JarvisIntent(intent="create_folder", confidence=0.96, slots=slots)


def run_create_folder(intent: JarvisIntent) -> "JarvisActionResult":
    from pathlib import Path

    from helpers.jarvis_local import resolve_existing_path
    from schemas.jarvis import JarvisActionResult

    user_text = (intent.slots.get("user_text") or "").strip()
    if user_text and not (intent.slots.get("name") or "").strip():
        parsed = parse_create_folder_intent(user_text)
        if parsed:
            intent = parsed

    name = _clean_folder_name(
        (
            intent.slots.get("name")
            or intent.slots.get("folder_name")
            or intent.slots.get("folder")
            or ""
        ).strip().strip('"').strip("'")
    )
    parent_raw = (intent.slots.get("parent") or intent.slots.get("path") or "").strip()
    if not parent_raw and user_text:
        parent_raw = _normalize_parent(None, user_text) or ""
    context_path = (intent.slots.get("context_path") or "").strip()
    if not parent_raw and context_path:
        try:
            cp = Path(context_path)
            parent_raw = str(cp) if cp.is_dir() else str(cp.parent)
        except OSError:
            parent_raw = context_path

    if parent_raw and name:
        parent = resolve_existing_path(parent_raw) or parent_raw
        folder = Path(parent) / name
    elif parent_raw and not name:
        folder = Path(resolve_existing_path(parent_raw) or parent_raw)
    else:
        return JarvisActionResult(
            False,
            "Tell me where to create the folder and what to name it.",
            "create_folder",
        )

    try:
        folder = folder.resolve()
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return JarvisActionResult(
            False,
            f"Could not create folder: {exc}",
            "create_folder",
        )

    return JarvisActionResult(
        True,
        f"Created folder {folder.name} at {folder.parent}.",
        "create_folder",
        target_label=str(folder),
    )


def content_looks_like_folder_not_file(content: str) -> bool:
    low = " ".join(content.lower().split())
    if "folder" not in low:
        return False
    return bool(
        re.search(r"\bcreate\b", low)
        or re.search(r"\b(named|called|name\s+as)\b", low)
        or re.search(r"\bfolder\s+name\b", low)
    )
