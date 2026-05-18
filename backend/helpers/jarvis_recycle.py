"""Recycle Bin — open folder or empty everything in one shot (no per-file UI)."""

from __future__ import annotations

import os
import re

_RECYCLE_WORD = re.compile(r"\b(recycle\s*bin|recyclebin|recycle|trash)\b", re.I)
_EMPTY_VERB = re.compile(
    r"\b("
    r"delete\s+all|remove\s+all|clear\s+all|empty|wipe|clean\s+out|"
    r"permanently\s+delete|purge|sab\s+delete|sara\s+delete|sab\s+khali|khali\s+karo"
    r")\b",
    re.I,
)
_OPEN_VERB = re.compile(r"\b(open|kholo|show|dikhao|launch|start)\b", re.I)

RECYCLE_BIN_TIMEOUT_SEC = int(os.getenv("JARVIS_RECYCLE_BIN_TIMEOUT", "600"))


def user_wants_empty_recycle_bin(text: str) -> bool:
    """User asked to delete / empty the Recycle Bin (all items at once)."""
    low = " ".join((text or "").lower().split())
    if not low:
        return False
    if re.search(r"\bempty\s+(the\s+)?(recycle\s+)?bin\b", low):
        return True
    if re.search(r"\bclear\s+(the\s+)?recycle\b", low):
        return True
    if not _RECYCLE_WORD.search(low):
        return False
    return bool(_EMPTY_VERB.search(low))


def user_wants_open_recycle_bin_only(text: str) -> bool:
    low = " ".join((text or "").lower().split())
    if not _RECYCLE_WORD.search(low):
        return False
    if user_wants_empty_recycle_bin(low):
        return False
    return bool(_OPEN_VERB.search(low) or low in ("recycle bin", "recycle", "trash"))


def is_recycle_bin_maintenance_command(text: str) -> bool:
    """Safe to allow 'delete all' wording — scoped to Recycle Bin only."""
    return user_wants_empty_recycle_bin(text) or user_wants_open_recycle_bin_only(text)


def empty_recycle_bin_powershell() -> str:
    """
    Fast empty: remove each drive's $Recycle.Bin folder via cmd (much faster than
  Clear-RecycleBin on huge bins). Falls back to Clear-RecycleBin if anything remains.
    """
    return r"""
$ErrorActionPreference = 'SilentlyContinue'
$cleared = [System.Collections.Generic.List[string]]::new()

foreach ($d in [System.IO.DriveInfo]::GetDrives()) {
    if (-not $d.IsReady) { continue }
    if ($d.DriveType -notin @('Fixed', 'Removable')) { continue }
    $root = $d.RootDirectory.FullName.TrimEnd('\')
    $rb = Join-Path $root '$Recycle.Bin'
    if (-not (Test-Path -LiteralPath $rb)) { continue }
    $null = & cmd.exe /c "rd /s /q `"$rb`""
    if (-not (Test-Path -LiteralPath $rb)) {
        New-Item -ItemType Directory -Path $rb -Force | Out-Null
    }
    $cleared.Add($d.Name)
}

$left = 0
try {
    $shell = New-Object -ComObject Shell.Application
    $left = @($shell.NameSpace(0x0a).Items()).Count
} catch { $left = 0 }

if ($left -gt 0 -and (Get-Command Clear-RecycleBin -ErrorAction SilentlyContinue)) {
    Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    try {
        $shell = New-Object -ComObject Shell.Application
        $left = @($shell.NameSpace(0x0a).Items()).Count
    } catch { }
}

if ($left -gt 0) {
    Write-Error "Recycle Bin still has $left item(s). Run Guardian backend as Administrator."
    exit 1
}

if ($cleared.Count -eq 0) {
    Write-Output 'Recycle Bin was already empty.'
} else {
    Write-Output ('Recycle Bin emptied on ' + ($cleared -join ', ') + '.')
}
"""


def open_recycle_bin_folder() -> tuple[bool, str]:
    import subprocess

    from helpers.jarvis_focus import focus_app_by_name

    try:
        subprocess.Popen(["explorer.exe", "shell:RecycleBinFolder"], shell=False)
        focus_app_by_name("Recycle Bin")
        return True, "Recycle Bin"
    except OSError as exc:
        return False, str(exc)


def empty_recycle_bin(*, open_folder_after: bool = False) -> tuple[bool, str]:
    from helpers.jarvis_powershell import run_powershell_script

    ok, msg = run_powershell_script(
        empty_recycle_bin_powershell(),
        timeout_sec=RECYCLE_BIN_TIMEOUT_SEC,
        single_threaded_apartment=False,
    )
    if not ok:
        if "timed out" in msg.lower():
            return (
                False,
                f"{msg} Large bins can take several minutes — try "
                f"JARVIS_RECYCLE_BIN_TIMEOUT=900 in backend .env.",
            )
        return False, msg

    out = msg.strip() or "Recycle Bin emptied."
    if open_folder_after:
        opened, _ = open_recycle_bin_folder()
        if opened:
            out = f"{out} Opened Recycle Bin."
    return True, out
