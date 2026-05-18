"""Detect when the user wants a visible terminal window vs a background command."""

from __future__ import annotations

import re


def user_wants_visible_terminal(text: str) -> bool:
    """
    True if the user asked to OPEN a terminal app on screen.
    False if they want to RUN a command (background PowerShell is correct).
    """
    low = " ".join((text or "").lower().split())
    if not low:
        return False

    if re.search(r"\b(run|execute)\s+(command|powershell|ps)\b", low):
        return False
    if re.search(r"\bpowershell\s*:", low) or re.search(r"\bcmd\s*:", low):
        return False
    if re.search(r"\b(list|show|get|dikhao|check|kill|stop)\b", low) and "open" not in low:
        return False

    return bool(
        re.search(
            r"\b(open|start|launch|kholo)\b.*\b(terminal|powershell|power\s*shell|cmd|command\s+prompt|console)\b",
            low,
        )
        or re.search(
            r"\b(terminal|powershell|cmd|console)\b.*\b(open|start|launch|kholo|window)\b",
            low,
        )
        or re.search(r"^open\s+(the\s+)?(terminal|powershell|cmd)\b", low)
        or low in ("terminal", "open terminal", "powershell", "open powershell", "cmd", "open cmd")
    )
