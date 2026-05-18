"""Detect chat apps and parse 'message to X …' phrasing."""

from __future__ import annotations

import re

_MESSAGING_KEYWORDS = (
    "whatsapp",
    "telegram",
    "discord",
    "teams",
    "slack",
    "messenger",
    "signal",
    "skype",
    "viber",
    "line",
    "wechat",
)

_MESSAGE_TO_RE = re.compile(
    r"^(?:write\s+)?(?:a\s+)?message\s+to\s+(.+)$",
    re.I,
)
_SEND_TO_RE = re.compile(
    r"^send\s+(?P<content>.+)\s+to\s+(?P<recipient>.+)$",
    re.I,
)
_TO_RECIPIENT_RE = re.compile(
    r"^to\s+(.+)$",
    re.I,
)
_CHAT_PHRASE_RE = re.compile(
    r"\b(?:message|text|sms)\s+to\b|\bsend\s+.+\s+to\b",
    re.I,
)


def is_messaging_app(name: str | None) -> bool:
    if not name:
        return False
    low = name.lower()
    return any(k in low for k in _MESSAGING_KEYWORDS)


def looks_like_chat_message(text: str) -> bool:
    return bool(_CHAT_PHRASE_RE.search((text or "").strip()))


def _split_recipient_and_body(rest: str) -> tuple[str, str]:
    """Last word = message; earlier words = contact name."""
    words = rest.split()
    if len(words) >= 2:
        return " ".join(words[:-1]).strip(), words[-1].strip()
    if len(words) == 1:
        return words[0], ""
    return rest, ""


def _strip_quotes(text: str) -> str:
    s = (text or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1].strip()
    return s


def parse_message_slots(content: str) -> tuple[str | None, str, bool]:
    """
    Parse chat phrasing. Returns (recipient, message_body, should_send).
    'send hello message to Manzar bhai' -> ('Manzar bhai', 'hello message', True)
    """
    raw = " ".join((content or "").strip().split())
    if not raw:
        return None, "", False

    m = _SEND_TO_RE.match(raw)
    if m:
        recipient = _strip_quotes(m.group("recipient").strip())
        body = _strip_quotes(m.group("content").strip())
        return recipient or None, body, True

    for pattern in (_MESSAGE_TO_RE, _TO_RECIPIENT_RE):
        m = pattern.match(raw)
        if m:
            recipient, body = _split_recipient_and_body(m.group(1).strip())
            recipient = _strip_quotes(recipient)
            body = _strip_quotes(body)
            return recipient or None, body, False

    return None, raw, raw.lower().startswith("send ")


def should_type_not_write(*, app: str | None, content: str) -> bool:
    return is_messaging_app(app) or looks_like_chat_message(content)
