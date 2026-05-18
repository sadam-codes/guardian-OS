"""Instagram DMs — Playwright DOM automation (reliable) with optional CDP to your open Chrome."""

from __future__ import annotations

import atexit
import logging
import os
import sys
import threading
import time
from pathlib import Path

from helpers.jarvis_focus import focus_browser_window
from helpers.jarvis_messaging import parse_message_slots

logger = logging.getLogger(__name__)

INSTAGRAM_INBOX = "https://www.instagram.com/direct/inbox/"
INSTAGRAM_NEW = "https://www.instagram.com/direct/new/"
_PROFILE_DIR = Path(__file__).resolve().parent.parent / ".jarvis-browser-profile"
_LOAD_DELAY = float(os.getenv("JARVIS_INSTAGRAM_DELAY_SEC", "3.0"))

try:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[misc, assignment]
    Browser = BrowserContext = Page = Playwright = None  # type: ignore[misc, assignment]

_pw: Playwright | None = None
_context: BrowserContext | None = None
_lock = threading.Lock()


def _gui_ready() -> bool:
    try:
        from helpers.jarvis_gui import _gui_ok  # noqa: PLC0415

        return _gui_ok()
    except Exception:
        return False


def _resolve_recipient_and_message(recipient: str, message: str) -> tuple[str, str]:
    if recipient:
        return recipient.strip(), message.strip()
    if message:
        parsed_recipient, parsed_body, _ = parse_message_slots(message)
        if parsed_recipient:
            return parsed_recipient, parsed_body
    return "", message.strip()


def _playwright_available() -> bool:
    return sync_playwright is not None


def _chrome_channel() -> str | None:
    ch = os.getenv("JARVIS_PLAYWRIGHT_CHANNEL", "chrome").strip()
    return ch or "chrome"


def _cdp_url() -> str | None:
    port = os.getenv("JARVIS_CHROME_DEBUG_PORT", "").strip()
    if port:
        return f"http://127.0.0.1:{port}"
    return None


def _shutdown() -> None:
    global _pw, _context
    with _lock:
        try:
            if _context:
                _context.close()
        except Exception:
            pass
        _context = None
        try:
            if _pw:
                _pw.stop()
        except Exception:
            pass
        _pw = None


atexit.register(_shutdown)


def _get_persistent_context() -> BrowserContext:
    global _pw, _context
    if _context is not None:
        return _context
    if not _playwright_available():
        raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chrome")
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    _pw = sync_playwright().start()
    channel = _chrome_channel()
    kwargs: dict = {
        "user_data_dir": str(_PROFILE_DIR),
        "headless": False,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    if channel:
        kwargs["channel"] = channel
    _context = _pw.chromium.launch_persistent_context(**kwargs)
    return _context


def _page_from_cdp() -> Page | None:
    url = _cdp_url()
    if not url or not _playwright_available():
        return None
    try:
        pw = sync_playwright().start()
        browser: Browser = pw.chromium.connect_over_cdp(url)
        if not browser.contexts:
            return None
        ctx = browser.contexts[0]
        for page in ctx.pages:
            if "instagram.com" in (page.url or ""):
                return page
        page = ctx.new_page() if ctx.pages else ctx.new_page()
        return page
    except Exception as exc:
        logger.debug("CDP connect failed: %s", exc)
        return None


def _active_page() -> Page:
    cdp_page = _page_from_cdp()
    if cdp_page is not None:
        return cdp_page
    ctx = _get_persistent_context()
    if ctx.pages:
        return ctx.pages[0]
    return ctx.new_page()


def open_instagram_url(url: str) -> tuple[bool, str | None]:
    """Open Instagram (for open_app only) — uses Playwright page or default browser."""
    if _playwright_available() and not _cdp_url():
        try:
            page = _active_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.bring_to_front()
            focus_browser_window()
            return True, None
        except Exception as exc:
            logger.warning("Playwright open Instagram failed: %s", exc)
    return _open_default_browser(url)


def _open_default_browser(url: str) -> tuple[bool, str | None]:
    try:
        if sys.platform == "win32":
            os.startfile(url)  # noqa: S606
            focus_browser_window()
        else:
            import webbrowser

            webbrowser.open(url)
        return True, None
    except OSError as exc:
        return False, str(exc)


def _click_first(locator, *, timeout: int = 12_000) -> bool:
    try:
        loc = locator.first
        loc.wait_for(state="visible", timeout=timeout)
        loc.click(timeout=timeout)
        return True
    except Exception:
        return False


def _fill_first(locator, text: str, *, timeout: int = 12_000) -> bool:
    try:
        loc = locator.first
        loc.wait_for(state="visible", timeout=timeout)
        loc.click(timeout=3000)
        loc.fill(text, timeout=timeout)
        return True
    except Exception:
        return False


def _open_chat_from_inbox(page: Page, recipient: str) -> bool:
    page.goto(INSTAGRAM_INBOX, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(int(_LOAD_DELAY * 1000))

    search = page.locator(
        'input[placeholder*="Search"], input[aria-label="Search"], input[type="search"]'
    )
    if _fill_first(search, recipient):
        page.wait_for_timeout(2000)
        for loc in (
            page.get_by_role("link", name=recipient),
            page.locator(f'a[href*="/direct/t/"]:has-text("{recipient}")'),
            page.get_by_text(recipient, exact=False),
        ):
            if _click_first(loc, timeout=5000):
                page.wait_for_timeout(1200)
                return True
    return False


def _open_chat_new_message(page: Page, recipient: str) -> bool:
    page.goto(INSTAGRAM_NEW, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(int(_LOAD_DELAY * 1000))

    search = page.locator(
        'input[placeholder*="Search"], input[name="queryBox"], input[aria-label="Search"]'
    )
    if not _fill_first(search, recipient):
        return False

    page.wait_for_timeout(2200)

    for loc in (
        page.locator('input[type="checkbox"]').first,
        page.get_by_role("button", name=recipient),
        page.locator(f'div[role="button"]:has-text("{recipient}")'),
        page.locator('motion.div[role="button"]').first,
    ):
        if _click_first(loc, timeout=4000):
            break
    else:
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(250)
        page.keyboard.press("Enter")

    page.wait_for_timeout(800)
    for name in ("Chat", "Next", "Done"):
        if _click_first(page.get_by_role("button", name=name), timeout=3000):
            break

    page.wait_for_timeout(1200)
    return True


def _type_and_send(page: Page, message: str, *, send: bool) -> bool:
    compose = page.locator(
        'motion.textarea textarea, '
        'div[contenteditable="true"][role="textbox"], '
        'motion.textarea textarea, '
        'div[contenteditable="true"], '
        'textarea[placeholder*="Message"], '
        'textarea'
    )
    if not _fill_first(compose, message):
        return False
    if send:
        page.wait_for_timeout(400)
        try:
            page.get_by_role("button", name="Send").first.click(timeout=3000)
        except Exception:
            page.keyboard.press("Enter")
    return True


def _playwright_send_dm(recipient: str, message: str, *, send: bool) -> tuple[bool, str | None]:
    page = _active_page()
    page.bring_to_front()
    focus_browser_window()

    opened = False
    if recipient:
        opened = _open_chat_from_inbox(page, recipient)
        if not opened:
            opened = _open_chat_new_message(page, recipient)
        if not opened:
            return False, (
                f"Could not find {recipient} on Instagram. "
                "Log in to Instagram in the Guardian Chrome window (first time only)."
            )

    if message:
        if not _type_and_send(page, message, send=send):
            return False, "Could not find the message box. Open the chat manually once, then retry."

    return True, None


def instagram_send_message(
    recipient: str,
    message: str,
    *,
    send: bool = True,
) -> tuple[bool, str | None]:
    recipient, message = _resolve_recipient_and_message(recipient, message)
    if not recipient and not message:
        return False, "Who should I message on Instagram?"

    if not _playwright_available():
        return False, "Instagram DMs need Playwright. Run: pip install playwright && playwright install chrome"

    try:
        with _lock:
            return _playwright_send_dm(recipient, message, send=send)
    except Exception as exc:
        logger.warning("Instagram DM failed: %s", exc)
        return False, str(exc)
