"""Local path / shell hints without regex — Groq does most language understanding."""

from __future__ import annotations

import shutil
from pathlib import Path

from schemas.jarvis import JarvisIntent

_TERMINAL_TOKENS = frozenset(
    {
        "terminal",
        "wt",
        "wt.exe",
        "cmd.exe",
        "pwsh",
        "powershell",
        "console",
        "shell",
        "cmd",
    }
)
_WEB_SEARCH_MARKERS = frozenset({"google", "bing", "duckduckgo", "web", "internet", "online"})
_SEARCH_WORDS = frozenset({"search", "googling", "lookup", "look", "browse"})


def _norm_word(token: str) -> str:
    return token.strip().strip(".,!?;:\"'").lower()


def _words(text: str) -> list[str]:
    return [w for w in text.strip().split() if w]


def _explicit_open_command(clean: str) -> bool:
    words = _words(clean)
    polite = {
        "please",
        "can",
        "you",
        "could",
        "would",
        "will",
        "the",
        "a",
        "an",
        "to",
        "me",
        "my",
        "hey",
        "hi",
        "hello",
    }
    i = 0
    while i < len(words) and i < 8:
        if _norm_word(words[i]) in polite:
            i += 1
            continue
        break
    rest = words[i : i + 4]
    if not rest:
        return False
    head = {_norm_word(w) for w in rest}
    return bool(
        head
        & {
            "open",
            "launch",
            "start",
            "run",
            "show",
            "go",
            "jao",
            "kholo",
            "khol",
        }
    )


def _is_web_search_context(words: list[str]) -> bool:
    nw = {_norm_word(w) for w in words}
    if not (nw & _SEARCH_WORDS):
        return False
    if nw & _WEB_SEARCH_MARKERS:
        return True
    joined = " ".join(_norm_word(w) for w in words)
    return "look up" in joined or "look-up" in joined


def _wants_terminal(clean: str, words: list[str]) -> bool:
    if _is_web_search_context(words):
        return False
    low = clean.lower()
    if "command prompt" in low or "windows terminal" in low:
        return True
    nw = {_norm_word(w) for w in words}
    return bool(nw & _TERMINAL_TOKENS)


def _terminal_shell_choice(clean_lower: str, words: list[str]) -> str:
    if "command prompt" in clean_lower or _norm_word(words[-1] if words else "") == "cmd":
        return "cmd"
    if "powershell" in clean_lower or "pwsh" in clean_lower or "pwsh" in {_norm_word(w) for w in words}:
        return "powershell"
    return "wt"


def _drive_from_words(words: list[str]) -> str | None:
    for i, w in enumerate(words):
        if _norm_word(w) != "drive" or i == 0:
            continue
        prev = _norm_word(words[i - 1])
        if len(prev) == 1 and prev.isascii() and prev.isalpha():
            return f"{prev.upper()}:\\"
    return None


def _forbidden_path_char(ch: str) -> bool:
    return ch in '<>|"?\n\r\t'


def _scan_windows_path(text: str) -> str | None:
    n = len(text)
    i = 0
    while i < n - 1:
        c, nxt = text[i], text[i + 1]
        if _is_drive_letter(c) and nxt == ":":
            prev = text[i - 1] if i > 0 else " "
            if prev in ' \t("\'[' or i == 0:
                j = i + 2
                if j < n and text[j] in "/\\":
                    while j < n and not _forbidden_path_char(text[j]) and text[j] not in " \t":
                        j += 1
                    candidate = text[i:j].rstrip("/\\")
                    if len(candidate) >= 3:
                        return candidate
                else:
                    while j < n and text[j] in " \t":
                        j += 1
                    if j >= n or text[j] in ".,);":
                        return f"{c.upper()}:\\"
            i += 1
            continue
        i += 1
    return None


def _is_drive_letter(ch: str) -> bool:
    return len(ch) == 1 and ch.isascii() and ch.isalpha()


def _scan_unc(text: str) -> str | None:
    for raw_t in text.split():
        t = raw_t.strip().strip(".,!?;:\"'")
        if len(t) > 3 and t.startswith("\\\\"):
            return t
    i = text.find("\\\\")
    if i < 0:
        return None
    j = i
    while j < len(text) and text[j] not in " \t":
        j += 1
    cand = text[i:j].strip().strip(".,!?;:\"'")
    return cand if len(cand) > 3 else None


def extract_path_candidate(text: str) -> str | None:
    """Best-effort Windows path from free text (no regex)."""
    from helpers.jarvis_web import looks_like_web_search

    clean = " ".join(text.strip().split())
    if not clean:
        return None
    allow_loose_path = _explicit_open_command(clean) or not looks_like_web_search(clean)

    unc = _scan_unc(clean)
    if unc and allow_loose_path:
        return unc

    scanned = _scan_windows_path(clean)
    if scanned and allow_loose_path:
        return scanned.rstrip("/\\")

    words = _words(clean)
    drive = _drive_from_words(words)
    if drive:
        return drive

    compact = clean.replace(" ", "")
    if allow_loose_path:
        for i in range(len(compact) - 1):
            if _is_drive_letter(compact[i]) and compact[i + 1] == ":":
                tail = compact[i + 2 : i + 3]
                if not tail or tail in "/\\":
                    return f"{compact[i].upper()}:\\"
                break

    s = clean.strip().strip('"').strip("'")
    if s.startswith("~") and (len(s) == 1 or s[1] in "/\\"):
        return str(Path.home()) + s[1:]

    return None


def try_local_intent(text: str) -> JarvisIntent | None:
    """Obvious filesystem / shell utterances when LLM is off or as a sanitizer."""
    clean = " ".join(text.strip().split())
    if not clean:
        return None

    words = _words(clean)
    if _wants_terminal(clean, words):
        shell = _terminal_shell_choice(clean.lower(), words)
        return JarvisIntent(intent="open_terminal", confidence=0.96, slots={"shell": shell})

    path_guess = extract_path_candidate(clean)
    if path_guess:
        return JarvisIntent(intent="open_path", confidence=0.94, slots={"path": path_guess})

    return None


def os_path_expand(s: str) -> str:
    import os

    return os.path.expandvars(os.path.expanduser(s))


def _norm_path_str(raw: str) -> str:
    s = raw.strip().strip('"').strip("'")
    if s.startswith("~") and (len(s) == 1 or s[1] in "/\\"):
        s = str(Path.home()) + s[1:]
    return str(Path(os_path_expand(s)))


def launch_shell(shell: str) -> tuple[bool, str]:
    """Start Windows Terminal, PowerShell, or CMD. Returns (ok, label)."""
    from helpers.jarvis_focus import focus_app_by_name

    shell = (shell or "wt").lower()
    if shell == "cmd":
        order = ["cmd"]
    elif shell == "powershell":
        order = ["pwsh", "powershell"]
    else:
        order = ["wt", "wt.exe", "pwsh", "powershell", "cmd"]

    for name in order:
        exe = shutil.which(name)
        if exe:
            import subprocess

            subprocess.Popen([exe])
            label = Path(exe).name
            focus_name = {
                "wt": "Windows Terminal",
                "wt.exe": "Windows Terminal",
                "pwsh": "PowerShell",
                "powershell": "Windows PowerShell",
                "cmd": "Command Prompt",
            }.get(name.lower(), label)
            focus_app_by_name(focus_name)
            return True, label

    return False, shell


def resolve_existing_path(raw: str) -> Path | None:
    """Resolve user path; return None if it does not exist."""
    try:
        p = Path(_norm_path_str(raw))
    except (OSError, ValueError):
        return None
    if p.exists():
        return p
    return None
