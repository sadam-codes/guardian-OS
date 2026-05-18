"""Translate voice to PowerShell and run with full Windows system access (System32 root)."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess

from helpers.jarvis_system import build_system_context_block, is_admin, system_root

logger = logging.getLogger(__name__)

ALLOW_POWERSHELL = os.getenv("JARVIS_ALLOW_POWERSHELL", "true").lower() in ("1", "true", "yes")
_MAX_OUTPUT_CHARS = int(os.getenv("JARVIS_POWERSHELL_MAX_OUTPUT", "2000"))
_TIMEOUT_SEC = int(os.getenv("JARVIS_POWERSHELL_TIMEOUT", "60"))
_RECYCLE_BIN_TIMEOUT_SEC = int(os.getenv("JARVIS_RECYCLE_BIN_TIMEOUT", "600"))

_BLOCKED_PS_PATTERNS = [
    (re.compile(r"\bFormat-Volume\b", re.I), "disk format"),
    (re.compile(r"\bClear-Disk\b", re.I), "disk wipe"),
    (
        re.compile(
            r"\bRemove-Item\b.*-Recurse\b.*(?:\\|/)?['\"]?(?:C:\\|C:/|\$env:SystemDrive\\|\$env:SystemDrive/)",
            re.I,
        ),
        "recursive delete on system drive root",
    ),
    (re.compile(r"\bInvoke-Expression\b.*(?:http|https|IEX)", re.I), "remote code execution"),
    (re.compile(r"\bSet-MpPreference\b.*-Disable", re.I), "disable Defender"),
    (re.compile(r"\bStop-Computer\b|\bRestart-Computer\b", re.I), "use shutdown/restart voice command"),
    (re.compile(r"\bdiskpart\b", re.I), "diskpart"),
    (re.compile(r"\bbcdedit\b.*/delete", re.I), "boot config delete"),
]

_SYSTEM_PREAMBLE = """
$ErrorActionPreference = 'Continue'
$JarvisSystemRoot = '{root}'
if (Test-Path -LiteralPath $JarvisSystemRoot) {{ Set-Location -LiteralPath $JarvisSystemRoot }}
"""


def powershell_enabled() -> bool:
    return ALLOW_POWERSHELL and os.name == "nt"


def extract_raw_powershell(speech: str) -> str | None:
    clean = " ".join(speech.strip().split())
    patterns = [
        r"^(?:please\s+)?(?:run|execute)\s+(?:this\s+)?(?:powershell|ps)\s*(?:command\s+)?(?:\:|;)?\s*(.+)$",
        r"^(?:please\s+)?(?:in\s+)?powershell\s*(?:\:|;)?\s*(.+)$",
        r"^(?:please\s+)?powershell\s+run\s+(.+)$",
        r"^(?:please\s+)?cmd\s*(?:\:|;)?\s*(.+)$",
    ]
    for pat in patterns:
        m = re.match(pat, clean, re.I)
        if m:
            return m.group(1).strip()
    return None


def validate_powershell_script(script: str) -> tuple[bool, str | None]:
    if not script.strip():
        return False, "No command to run."
    for pattern, reason in _BLOCKED_PS_PATTERNS:
        if pattern.search(script):
            return False, f"Blocked for safety: {reason}."
    return True, None


def _wrap_for_system_access(script: str) -> str:
    root = system_root().replace("'", "''")
    body = script.strip()
    if body.lower().startswith("cmd ") or body.lower().startswith("cmd.exe"):
        inner = body[3:].strip() if body.lower().startswith("cmd ") else body[7:].strip()
        body = f"cmd.exe /c {inner}"
    return _SYSTEM_PREAMBLE.format(root=root) + "\n" + body


def translate_to_powershell(natural_language: str) -> tuple[str, str] | None:
    from helpers.jarvis_groq import _chat, groq_enabled

    if not groq_enabled():
        return None

    ctx = build_system_context_block()
    system = (
        "You are the Windows SYSTEM executor for Guardian. "
        "The shell root is C:\\Windows\\System32 — you have access to the ENTIRE PC via PowerShell. "
        "Reply JSON only: {\"powershell\":\"...\",\"summary\":\"short label\"}. "
        "Write PowerShell that can touch any drive (C:\\ D:\\), registry, services, processes, "
        "files under Users and Program Files, network adapters, firewall, installed software. "
        "Start scripts from system root; use full paths when needed. Max 40 lines. "
        "Allowed: Get-Process, Stop-Process, Get-Service, Start-Service, Get-Item, Set-Item, "
        "New-Item, Remove-Item (not C:\\ root recurse), reg query/add, netsh, sc, wmic, Get-CimInstance, "
        "Get-Volume, explorer shell:*, Start-Process, Get-LocalUser, Get-NetAdapter. "
        "To empty Recycle Bin use ONLY: Clear-RecycleBin -Force (all items at once). "
        "Never delete recycle files one-by-one in a loop. "
        "BLOCKED only: Format-Volume, Clear-Disk, disable Defender, IEX download, diskpart wipe, bcdedit /delete."
    )
    user = f"{ctx}\n\nUser request: \"{natural_language}\""
    raw = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=500,
        temperature=0.1,
    )
    if not raw:
        return None
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        ps = str(data.get("powershell", "")).strip()
        summary = str(data.get("summary", "command")).strip() or "command"
        if not ps:
            return None
        return ps, summary
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("Groq PowerShell JSON parse failed: %s", raw[:200])
        return None


def _format_output(stdout: str, stderr: str, *, success: bool) -> str:
    parts: list[str] = []
    if stdout.strip():
        parts.append(stdout.strip())
    if stderr.strip() and (not success or not stdout.strip()):
        parts.append(stderr.strip())
    text = "\n".join(parts) if parts else ("Done." if success else "Command failed with no output.")
    if len(text) > _MAX_OUTPUT_CHARS:
        text = text[:_MAX_OUTPUT_CHARS] + "\n… (output trimmed)"
    admin_note = ""
    if not is_admin():
        admin_note = "\n(Tip: run Guardian backend as Administrator for changes that need admin.)"
    return text + admin_note


def run_powershell_script(
    script: str,
    *,
    timeout_sec: int | None = None,
    single_threaded_apartment: bool = True,
) -> tuple[bool, str]:
    if not powershell_enabled():
        return False, "PowerShell control is disabled. Set JARVIS_ALLOW_POWERSHELL=true in .env."

    safe, reason = validate_powershell_script(script)
    if not safe:
        return False, reason or "Command blocked."

    full_script = _wrap_for_system_access(script)
    root = system_root()
    limit = timeout_sec if timeout_sec is not None else _TIMEOUT_SEC

    ps_args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
    ]
    if single_threaded_apartment:
        ps_args.append("-Sta")
    ps_args.extend(["-Command", full_script])

    try:
        proc = subprocess.run(
            ps_args,
            capture_output=True,
            text=True,
            timeout=limit,
            cwd=root,
        )
    except subprocess.TimeoutExpired:
        return (
            False,
            f"PowerShell timed out after {limit} seconds. "
            f"For a large Recycle Bin, set JARVIS_RECYCLE_BIN_TIMEOUT higher in .env.",
        )
    except OSError as exc:
        return False, f"Could not run PowerShell: {exc}"

    ok = proc.returncode == 0
    msg = _format_output(proc.stdout or "", proc.stderr or "", success=ok)
    return ok, msg


def run_voice_command(speech: str, *, script_hint: str | None = None) -> tuple[bool, str, str | None]:
    from helpers.jarvis_recycle import empty_recycle_bin, user_wants_empty_recycle_bin

    if user_wants_empty_recycle_bin(speech):
        ok, msg = empty_recycle_bin(open_folder_after=False)
        return ok, msg, "Clear-RecycleBin -Force"

    raw = (script_hint or "").strip() or extract_raw_powershell(speech)
    if raw:
        ok, msg = run_powershell_script(raw)
        return ok, msg, raw

    translated = translate_to_powershell(speech)
    if not translated:
        return (
            False,
            "Set GROQ_API_KEY in backend .env so I can translate your request into PowerShell.",
            None,
        )

    from helpers.jarvis_terminal_detect import user_wants_visible_terminal

    if user_wants_visible_terminal(speech):
        from helpers.jarvis_local import launch_shell

        ok, label = launch_shell("wt")
        if ok:
            return True, f"Opened {label} in a new window.", label
        return False, "Could not open a visible terminal window.", None

    script, summary = translated
    ok, msg = run_powershell_script(script)
    prefix = f"{summary}: " if summary and ok else ""
    return ok, f"{prefix}{msg}" if ok else msg, script
