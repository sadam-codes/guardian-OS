import re

RISKY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(format|wipe|delete\s+all|rm\s+-rf)\b", re.I), "destructive disk operation"),
    (re.compile(r"\b(ransomware|malware|virus|keylogger)\b", re.I), "malicious software reference"),
    (re.compile(r"\b(password|credential|api[_\s]?key|secret)\b.*\b(send|email|upload)\b", re.I), "credential exfiltration"),
    (re.compile(r"\bdisable\s+(firewall|defender|antivirus)\b", re.I), "security disable"),
]

CONFIRM_INTENTS = {"shutdown", "restart", "lock"}

BLOCKED_WITHOUT_VERIFY = {"shutdown", "restart", "lock", "open_terminal", "run_project"}


def validate_command_safety(
    text: str,
    *,
    identity_verified: bool,
    intent_hint: str | None = None,
) -> tuple[bool, str | None]:
    stripped = text.strip()
    if not stripped:
        return False, "Empty command."

    for pattern, reason in RISKY_PATTERNS:
        if pattern.search(stripped):
            return False, f"Blocked for safety: {reason}."

    low = stripped.lower()
    if intent_hint in CONFIRM_INTENTS or any(
        kw in low for kw in ("shut down", "shutdown", "restart", "lock computer", "lock the")
    ):
        if not identity_verified:
            return False, "Identity must be verified before system lock or power commands."

    if intent_hint in BLOCKED_WITHOUT_VERIFY and not identity_verified:
        return False, "Verify your face in the Guardian camera before this command."

    return True, None
