"""Resolve spoken 'open X' targets to browser URLs when appropriate."""

import re
from urllib.parse import quote

KNOWN_SITES: dict[str, str] = {
    "github": "https://github.com",
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "twitter": "https://x.com",
    "gmail": "https://mail.google.com",
    "outlook": "https://outlook.live.com",
    "chatgpt": "https://chat.openai.com",
}

_DOMAIN_RE = re.compile(
    r"^[\w-]+(\.[\w-]+)*\.(com|org|net|edu|gov|pk|io|co|app)(/\S*)?$",
    re.I,
)


def _clean_query(raw: str) -> str:
    q = " ".join(raw.strip().split())
    for prefix in ("please ", "can you ", "could you ", "open ", "launch ", "go to "):
        if q.lower().startswith(prefix):
            q = q[len(prefix) :]
    for prefix in ("my ", "the ", "a ", "an "):
        if q.lower().startswith(prefix):
            q = q[len(prefix) :]
    return q.strip()


def resolve_web_open(raw: str) -> tuple[str, str] | None:
    """
    If the target should open in a browser, return (url, display_label).
    Otherwise return None so the Windows app launcher handles it.
    """
    q = _clean_query(raw)
    if not q:
        return None

    lower = q.lower()

    if lower.startswith("http://") or lower.startswith("https://"):
        return q, q

    if _DOMAIN_RE.match(lower):
        url = q if q.startswith("http") else f"https://{q}"
        return url, q

    web_hint = bool(
        re.search(r"\b(website|web\s*site|webpage|home\s*page|site)\b", lower)
        or lower.endswith(" site")
    )
    name = re.sub(r"\s*(website|web\s*site|webpage|home\s*page|site)\s*$", "", lower, flags=re.I).strip()
    if not name:
        name = lower

    if name in KNOWN_SITES:
        label = name.title() if name != "github" else "GitHub"
        return KNOWN_SITES[name], label

    if web_hint:
        slug = name.replace(" ", "")
        guesses = [
            f"https://www.{slug}.edu.pk",
            f"https://www.{slug}.edu",
            f"https://{slug}.edu.pk",
            f"https://www.{slug}.com",
            f"https://{slug}.com",
        ]
        return guesses[0], name.title()

    if name == "youtube" or lower.startswith("youtube"):
        return KNOWN_SITES["youtube"], "YouTube"

    return None


def youtube_search_url(query: str) -> str:
    clean = query.strip().strip("'\"")
    return f"https://www.youtube.com/results?search_query={quote(clean)}"
