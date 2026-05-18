"""Windows system context for Groq — full PC access via System32 root."""

from __future__ import annotations

import os
import subprocess
import sys

DEFAULT_SYSTEM_ROOT = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")


def system_root() -> str:
    custom = os.getenv("JARVIS_POWERSHELL_ROOT", "").strip().strip('"')
    if custom and os.path.isdir(custom):
        return custom
    if os.path.isdir(DEFAULT_SYSTEM_ROOT):
        return DEFAULT_SYSTEM_ROOT
    return os.path.expanduser("~")


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


def list_drives() -> list[str]:
    if sys.platform != "win32":
        return []
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-PSDrive -PSProvider FileSystem).Name"],
            capture_output=True,
            text=True,
            timeout=8,
            cwd=system_root(),
        )
        if proc.returncode == 0 and proc.stdout:
            return [f"{n.strip()}:" for n in proc.stdout.splitlines() if n.strip()]
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ["C:"]


def build_system_context_block() -> str:
    """Short facts for Groq — dynamic, not a static command list."""
    root = system_root()
    drives = ", ".join(list_drives()) or "C:"
    admin = "yes" if is_admin() else "no (run Guardian backend as Administrator for full control)"
    user = os.environ.get("USERNAME", "user")
    computer = os.environ.get("COMPUTERNAME", "PC")
    return (
        f"Windows system executor context:\n"
        f"- Shell root (default cwd): {root}\n"
        f"- User: {user} on {computer}\n"
        f"- Elevated admin: {admin}\n"
        f"- Drives: {drives}\n"
        f"- Full system access via PowerShell: all drives, registry (read/write careful), "
        f"services, processes, network, installed apps, env vars, scheduled tasks.\n"
        f"- Use Set-Location, Get-ChildItem, Get-CimInstance, Get-Service, reg.exe, netsh, sc.exe as needed.\n"
        f"- Paths like C:\\\\Users, C:\\\\Program Files, {root} are all allowed."
    )
