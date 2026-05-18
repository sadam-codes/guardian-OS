"""Open Windows shell namespaces and Start Menu shortcuts by spoken name."""

from __future__ import annotations

import os
import subprocess
import time

from helpers.jarvis_focus import focus_app_by_name

# Windows documents these shell: URIs — not per-machine app installs.
_SHELL_RESOLVE_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$q = ($env:JARVIS_SHELL_QUERY -replace '\s+', ' ').Trim().ToLower()
if (-not $q) { exit 1 }

function Open-Explorer([string]$Uri, [string]$Label) {
    $null = Start-Process explorer.exe -ArgumentList $Uri
    Write-Output $Label
    exit 0
}

# Fuzzy match: spoken phrase -> shell: target
$rows = @(
    @{ re='^(the\s+)?recycle\s*bin$|^recycle\s*bin$|^recycle$|^trash$'; u='shell:RecycleBinFolder'; l='Recycle Bin' },
    @{ re='^(the\s+)?control\s*panel$|^control\s*panel$'; u='shell:ControlPanelFolder'; l='Control Panel' },
    @{ re='^(this\s+)?(pc|computer)$|^(my\s+)?computer$|^this\s+pc$'; u='shell:MyComputerFolder'; l='This PC' },
    @{ re='^network(\s+places)?$|^my\s+network$'; u='shell:NetworkPlacesFolder'; l='Network' },
    @{ re='^printers(\s*(and\s*)?devices)?$|^devices\s+and\s+printers$'; u='shell:PrintersFolder'; l='Printers' },
    @{ re='^fonts$'; u='shell:FontsFolder'; l='Fonts' },
    @{ re='^downloads(\s+folder)?$'; u='shell:Downloads'; l='Downloads' },
    @{ re='^documents(\s+folder)?$'; u='shell:DocumentsLibrary'; l='Documents' },
    @{ re='^pictures(\s+folder)?$'; u='shell:PicturesLibrary'; l='Pictures' },
    @{ re='^music(\s+folder)?$'; u='shell:MusicLibrary'; l='Music' },
    @{ re='^videos(\s+folder)?$'; u='shell:VideosLibrary'; l='Videos' },
    @{ re='^desktop(\s+folder)?$'; u='shell:Desktop'; l='Desktop' },
    @{ re='^home(\s+folder)?$|^user\s+profile$|^profile$'; u='shell:Profile'; l='Home' }
)
foreach ($row in $rows) {
    if ($q -match $row.re) { Open-Explorer $row.u $row.l }
}

# Scan Start Menu shortcuts (dynamic — matches display names on this PC)
$menuRoots = @(
    "$env:ProgramData\Microsoft\Windows\Start Menu",
    "$env:APPDATA\Microsoft\Windows\Start Menu"
)
$best = $null
$bestScore = 0
$words = @($q -split '\s+' | Where-Object { $_.Length -gt 0 })

foreach ($root in $menuRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    Get-ChildItem -LiteralPath $root -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
        $nl = $name.ToLower()
        $score = 0
        if ($nl -eq $q) { $score = 100 }
        elseif ($nl -like "*$q*") { $score = 88 }
        else {
            $hits = 0
            foreach ($w in $words) {
                if ($w.Length -gt 1 -and $nl -like "*$w*") { $hits++ }
            }
            if ($words.Count -gt 0 -and $hits -eq $words.Count) { $score = 62 + $hits }
        }
        if ($score -gt $bestScore) {
            $bestScore = $score
            $best = $_
        }
    }
}

if ($best -and $bestScore -ge 60) {
    $sh = New-Object -ComObject WScript.Shell
    $sc = $sh.CreateShortcut($best.FullName)
    $target = $sc.TargetPath
    $args = $sc.Arguments
    if ($target) {
        if ($args) {
            Start-Process -FilePath $target -ArgumentList $args
        } else {
            Start-Process -FilePath $target
        }
        $label = [System.IO.Path]::GetFileNameWithoutExtension($best.Name)
        Write-Output $label
        exit 0
    }
}x`

exit 1
"""


def try_open_shell_target(raw: str) -> tuple[bool, str]:
    """Recycle Bin, libraries, and Start Menu shortcuts — not only Get-StartApps."""
    query = " ".join((raw or "").strip().split())
    if not query or os.name != "nt":
        return False, ""

    env = {**os.environ, "JARVIS_SHELL_QUERY": query}
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Sta",
                "-Command",
                _SHELL_RESOLVE_SCRIPT,
            ],
            capture_output=True,
            text=True,
            timeout=25,
            env=env,
            cwd=os.path.expanduser("~"),
        )
    except (subprocess.TimeoutExpired, OSError):
        return False, ""

    if proc.returncode != 0:
        return False, ""

    lines = [ln.strip() for ln in (proc.stdout or "").strip().splitlines() if ln.strip()]
    if not lines:
        return False, ""

    label = lines[-1]
    time.sleep(0.3)
    focus_app_by_name("Explorer")
    focus_app_by_name(label)
    return True, label
