"""Resolve spoken 'open X' targets to browser URLs when appropriate."""

import re
from urllib.parse import quote, urlparse

_SITE_LABELS: dict[str, str] = {
    "youtube.com": "YouTube",
    "google.com": "Google",
    "github.com": "GitHub",
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "x.com": "X",
    "twitter.com": "X",
    "mail.google.com": "Gmail",
    "outlook.live.com": "Outlook",
    "chat.openai.com": "ChatGPT",
}
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


def friendly_url_label(url: str) -> str:
    """Human label for speech/UI — never read raw https:// aloud."""
    raw = (url or "").strip()
    if not raw:
        return "that website"
    lower = raw.lower()
    if "youtube.com" in lower:
        return "YouTube"
    if "google.com" in lower:
        return "Google search" if "/search" in lower else "Google"
    for domain, label in _SITE_LABELS.items():
        if domain in lower:
            return label
    try:
        host = (urlparse(raw).hostname or "").lower()
    except ValueError:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    for domain, label in _SITE_LABELS.items():
        if host == domain or host.endswith(f".{domain}"):
            return label
    if host:
        return host.split(".")[0].title()
    return "that website"


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
        return q, friendly_url_label(q)

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
        return google_search_url(name), f"Google: {name.title()}"

    if name == "youtube" or lower.startswith("youtube"):
        return KNOWN_SITES["youtube"], "YouTube"

    return None


def google_search_url(query: str) -> str:
    clean = query.strip().strip("'\"")
    return f"https://www.google.com/search?q={quote(clean)}"


_SEARCH_HINTS = (
    "weather",
    "news",
    "price",
    "how to",
    "what is",
    "who is",
    "where is",
    "near me",
    "meaning",
    "translate",
    "convert",
    "recipe",
    "tutorial",
    "review",
)


def looks_like_web_search(query: str) -> bool:
    q = query.strip()
    if not q:
        return False
    lower = q.lower()
    if " in " in lower or lower.startswith("search "):
        return True
    if len(q.split()) >= 4:
        return True
    return any(hint in lower for hint in _SEARCH_HINTS)
