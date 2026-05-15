"""Dynamic Windows app launcher — discovers apps via Start menu."""

import os
import re
import subprocess
import sys
import time

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
    return name.strip()


def launch_windows_app(raw: str) -> tuple[bool, str]:
    """Launch an installed Windows app. Returns (success, display_label)."""
    query = normalize_app_query(raw)
    if not query:
        return False, ""

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
        return False, label

    time.sleep(0.3)
    return True, label
