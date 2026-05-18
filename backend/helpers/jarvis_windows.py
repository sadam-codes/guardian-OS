"""Dynamic Windows app launcher — discovers apps via Start menu."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time

from helpers.jarvis_focus import focus_app_by_name

# Spoken / Groq shortcuts -> Windows Start menu name (case as shown in Start)
_APP_ALIASES: dict[str, str] = {
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "vsc": "Visual Studio Code",
    "vs": "Visual Studio Code",
    "visual studio": "Visual Studio Code",
    "word": "Word",
    "ms word": "Word",
    "excel": "Excel",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "ms edge": "Microsoft Edge",
    "firefox": "Firefox",
    "notepad": "Notepad",
    "calc": "Calculator",
    "calculator": "Calculator",
    "settings": "Settings",
    "windows settings": "Settings",
    "task manager": "Task Manager",
    "spotify": "Spotify",
    "discord": "Discord",
    "teams": "Microsoft Teams",
    "zoom": "Zoom",
    "whatsapp": "WhatsApp",
    "whats app": "WhatsApp",
    "cursor": "Cursor",
    "powershell": "Windows PowerShell",
    "pwsh": "PowerShell",
    "terminal": "Windows Terminal",
    "wt": "Windows Terminal",
}

_LAUNCH_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$q = $env:JARVIS_APP_QUERY
if ([string]::IsNullOrWhiteSpace($q)) { exit 2 }

$q = $q.Trim()
$lower = $q.ToLower()

if ($lower -match 'setting') {
    Start-Process 'ms-settings:'
    Write-Output 'Windows Settings'
    exit 0
}

$apps = @(Get-StartApps)
$words = @($lower -split '\s+' | Where-Object { $_ })
$best = $null
$bestScore = 0

foreach ($app in $apps) {
    $nl = $app.Name.ToLower()
    $score = 0
    if ($nl -eq $lower) { $score = 100 }
    elseif ($nl -like "*$lower*") { $score = 85 }
    else {
        $hits = 0
        foreach ($w in $words) {
            if ($w.Length -gt 1 -and $nl -like "*$w*") { $hits++ }
        }
        if ($words.Count -gt 0 -and $hits -eq $words.Count) { $score = 60 + $hits }
    }
    if ($score -gt $bestScore) { $bestScore = $score; $best = $app }
}

if ($best -and $bestScore -ge 55) {
    $null = Start-Process 'explorer.exe' -ArgumentList "shell:AppsFolder\$($best.AppID)"
    Write-Output $best.Name
    exit 0
}

$exe = Get-Command $words[0] -ErrorAction SilentlyContinue
if ($exe) {
    $null = Start-Process $exe.Source
    Write-Output $exe.Name
    exit 0
}

# Let Windows resolve the name (chrome, notepad, code, etc.)
$p = Start-Process -FilePath $q -PassThru -ErrorAction SilentlyContinue
if ($p) {
    Write-Output $q
    exit 0
}

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'cmd.exe'
$psi.Arguments = '/c start "" ' + $q
$psi.UseShellExecute = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
[System.Diagnostics.Process]::Start($psi) | Out-Null
Start-Sleep -Milliseconds 500
Write-Output $q
exit 0
"""


def canonical_app_name(raw: str) -> str:
    """Map nicknames (vs code, vscode) to the Start menu application name."""
    name = " ".join(raw.strip().split())
    key = name.lower()
    if key in _APP_ALIASES:
        return _APP_ALIASES[key]
    for alias, full in sorted(_APP_ALIASES.items(), key=lambda item: -len(item[0])):
        if alias in key:
            return full
    return name


def normalize_app_query(raw: str) -> str:
    name = " ".join(raw.strip().split()).lower()
    for prefix in ("please ", "can you ", "could you "):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    for prefix in ("my ", "the ", "a ", "an "):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    name = re.sub(r"\b(window|windows)\s+", "", name)
    name = re.sub(r"\s+(app|application|program|software)$", "", name)
    return canonical_app_name(name.strip()).lower()


def _launch_vscode_cli() -> tuple[bool, str] | None:
    for exe in ("code", "code.cmd"):
        path = shutil.which(exe)
        if path:
            subprocess.Popen([path])  # noqa: S603
            focus_app_by_name("Visual Studio Code")
            return True, "Visual Studio Code"
    return None


def _is_vscode_query(query: str) -> bool:
    low = query.lower()
    return any(
        token in low
        for token in (
            "visual studio code",
            "vs code",
            "vscode",
            "vsc",
        )
    )


def launch_windows_app(raw: str) -> tuple[bool, str]:
    """Launch an installed Windows app. Returns (success, display_label)."""
    display = canonical_app_name(raw)
    query = normalize_app_query(raw)
    if not query:
        return False, ""

    if _is_vscode_query(query) or _is_vscode_query(display):
        cli = _launch_vscode_cli()
        if cli:
            return cli

    env = {**os.environ, "JARVIS_APP_QUERY": query}
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Sta",
                "-Command",
                _LAUNCH_SCRIPT,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=os.path.expanduser("~"),
        )
    except (subprocess.TimeoutExpired, OSError):
        return False, query.title()

    label = query.title()
    if proc.stdout:
        lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
        if lines:
            label = lines[-1]

    if proc.returncode != 0:
        if _is_vscode_query(query):
            cli = _launch_vscode_cli()
            if cli:
                return cli
        return False, display or label

    time.sleep(0.3)
    focus_app_by_name(display or label)
    return True, display or label
