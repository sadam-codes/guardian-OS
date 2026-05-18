"""Dynamic Windows app launcher — Start menu, shell folders, shortcuts."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time

from helpers.jarvis_focus import focus_app_by_name, focus_browser_window
from helpers.jarvis_shell import try_open_shell_target

# Only nicknames that differ from Start menu / shell names (not a full app list).
_APP_NICKNAMES: dict[str, str] = {
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "vsc": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "ms word": "Word",
    "google chrome": "Google Chrome",
    "ms edge": "Microsoft Edge",
    "windows settings": "Settings",
    "whats app": "WhatsApp",
    "insta": "Instagram",
    "ig": "Instagram",
    "browser": "__jarvis_browser__",
    "web browser": "__jarvis_browser__",
    "the browser": "__jarvis_browser__",
    "my browser": "__jarvis_browser__",
    "internet": "__jarvis_browser__",
    "the internet": "__jarvis_browser__",
    "default browser": "__jarvis_browser__",
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

$p = Start-Process -FilePath $q -PassThru -ErrorAction SilentlyContinue
if ($p) {
    Write-Output $q
    exit 0
}

exit 1
"""


def canonical_app_name(raw: str) -> str:
    """Map common nicknames; everything else passes through for dynamic lookup."""
    name = " ".join(raw.strip().split())
    key = name.lower()
    if key in _APP_NICKNAMES:
        mapped = _APP_NICKNAMES[key]
        if mapped == "__jarvis_browser__":
            return "browser"
        return mapped
    for alias, full in sorted(_APP_NICKNAMES.items(), key=lambda item: -len(item[0])):
        if len(alias) >= 3 and alias in key:
            if full == "__jarvis_browser__":
                return "browser"
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


def _is_browser_query(query: str) -> bool:
    from helpers.jarvis_web import is_generic_browser_request

    key = query.strip().lower()
    if is_generic_browser_request(query):
        return True
    return _APP_NICKNAMES.get(key) == "__jarvis_browser__"


def _launch_default_browser() -> tuple[bool, str]:
    import sys

    url = "https://www.google.com"
    if sys.platform == "win32":
        try:
            os.startfile(url)  # noqa: S606
            time.sleep(0.35)
            focus_browser_window()
            return True, "Browser"
        except OSError:
            pass
        for exe in ("msedge", "chrome", "firefox", "brave"):
            try:
                subprocess.Popen(  # noqa: S603
                    ["cmd", "/c", "start", "", exe],
                    shell=False,
                    cwd=os.path.expanduser("~"),
                )
                time.sleep(0.4)
                focus_browser_window()
                return True, "Browser"
            except OSError:
                continue
    else:
        try:
            import webbrowser

            webbrowser.open(url)
            return True, "Browser"
        except OSError:
            pass
    return False, "Browser"


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
    """Launch app, shell folder, or Start Menu item. Returns (success, display_label)."""
    display = canonical_app_name(raw)
    query = normalize_app_query(raw)
    if not query:
        return False, ""

    if _is_browser_query(raw) or _is_browser_query(query) or _is_browser_query(display):
        ok, label = _launch_default_browser()
        if ok:
            return True, label

    if _is_vscode_query(query) or _is_vscode_query(display):
        cli = _launch_vscode_cli()
        if cli:
            return cli

    shell_ok, shell_label = try_open_shell_target(raw)
    if not shell_ok and query != raw.lower():
        shell_ok, shell_label = try_open_shell_target(query)
    if shell_ok:
        return True, shell_label

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
        return False, display or query.title()

    label = display or query.title()
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
