"""Jarvis browser automation via Playwright (replaces webbrowser)."""

from __future__ import annotations

import atexit
import logging
import os
import threading
from typing import TYPE_CHECKING

from urllib.parse import quote

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from playwright.sync_api import Page

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[misc, assignment]


def _use_playwright() -> bool:
    return os.getenv("JARVIS_USE_PLAYWRIGHT", "true").lower() in ("1", "true", "yes")


class _BrowserSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pw = None
        self._browser = None
        self._page: Page | None = None

    def _reset(self) -> None:
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except Exception:
            pass
        self._page = None
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        self._browser = None
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = None

    def shutdown(self) -> None:
        with self._lock:
            self._reset()

    def _ensure_page_locked(self) -> Page:
        if sync_playwright is None:
            raise RuntimeError("playwright is not installed. pip install playwright && playwright install chromium")
        if self._page is not None and not self._page.is_closed():
            return self._page
        self._reset()
        self._pw = sync_playwright().start()
        headless = os.getenv("JARVIS_PLAYWRIGHT_HEADLESS", "false").lower() in ("1", "true", "yes")
        channel = os.getenv("JARVIS_PLAYWRIGHT_CHANNEL", "").strip() or None
        self._browser = self._pw.chromium.launch(headless=headless, channel=channel)
        self._page = self._browser.new_page()
        return self._page

    def goto(self, url: str) -> None:
        with self._lock:
            page = self._ensure_page_locked()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.bring_to_front()

    def dismiss_youtube_consent(self, page: Page) -> None:
        for name in ("Accept all", "Reject all", "I agree", "Accept", "Tout accepter"):
            try:
                btn = page.get_by_role("button", name=name)
                if btn.count() > 0:
                    btn.first.click(timeout=2500)
                    return
            except Exception:
                continue

    def youtube_search_and_play(self, query: str) -> None:
        with self._lock:
            page = self._ensure_page_locked()
            url = f"https://www.youtube.com/results?search_query={quote(query.strip())}"
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.bring_to_front()
            page.wait_for_timeout(1500)
            self.dismiss_youtube_consent(page)

            selectors = (
                "ytd-video-renderer a#video-title",
                "ytd-video-renderer h3 a#video-title",
                "ytd-video-renderer a[href^='/watch']",
                "a#video-title",
            )
            last_err: Exception | None = None
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    loc.wait_for(state="visible", timeout=12_000)
                    loc.click(timeout=10_000)
                    page.wait_for_timeout(1200)
                    self.dismiss_youtube_consent(page)
                    try:
                        play = page.locator(".ytp-large-play-button, .ytp-play-button").first
                        if play.is_visible(timeout=2000):
                            play.click(timeout=2000)
                    except Exception:
                        pass
                    return
                except Exception as exc:
                    last_err = exc
                    continue
            raise RuntimeError(f"Could not start playback: {last_err}")


_session = _BrowserSession()
atexit.register(_session.shutdown)


def jarvis_browser_goto(url: str) -> tuple[bool, str | None]:
    """Open URL in the managed Playwright browser. Returns (ok, error_message)."""
    if not _use_playwright():
        return _fallback_open_url(url)
    try:
        _session.goto(url)
        return True, None
    except Exception as exc:
        logger.warning("Playwright goto failed: %s", exc)
        return _fallback_open_url(url, str(exc))


def jarvis_youtube_play(query: str) -> tuple[bool, str | None]:
    """Search YouTube and click the first result to start playback."""
    if not _use_playwright():
        return _fallback_open_url(f"https://www.youtube.com/results?search_query={quote(query)}")
    try:
        _session.youtube_search_and_play(query)
        return True, None
    except Exception as exc:
        logger.warning("Playwright YouTube play failed: %s", exc)
        return _fallback_open_url(f"https://www.youtube.com/results?search_query={quote(query)}", str(exc))


def _fallback_open_url(url: str, playwright_err: str | None = None) -> tuple[bool, str | None]:
    """Windows default browser when Playwright is disabled or failed."""
    import sys

    try:
        if sys.platform == "win32":
            os.startfile(url)  # noqa: S606
        else:
            import webbrowser

            webbrowser.open(url)
        msg = None
        if playwright_err:
            msg = f"Opened in default browser (Playwright: {playwright_err})."
        return True, msg
    except OSError as exc:
        return False, str(exc)
