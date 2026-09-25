"""Cloudflare-protected page fetcher using a stealth-patched headless browser
(patchright) as a last-resort fallback for when a plain HTTP client (curl_cffi,
even with TLS impersonation) gets served a Cloudflare JS/Turnstile challenge
instead of the real page.

Kept as a separate, lazily-initialized module -- scripts that never hit a
Cloudflare wall don't pay the browser-launch cost, and one browser/context is
reused across every fetch within a run rather than relaunching per URL (that
would be far too slow to be worth it).

Reserved filename: this is one of `_NON_SCRAPER_FILES` in files_repo.py, so
it is never offered as a registerable scraper on its own -- it's a helper
other scraper scripts import.
"""

import threading
import time

_lock = threading.Lock()
_state = {}

_CHALLENGE_MARKERS = ("Just a moment", "challenges.cloudflare.com", "__cf_chl_rt_tk")


class BrowserResponse:
    """Minimal stand-in for a curl_cffi/requests Response so existing
    call sites (resp.status_code / resp.text / resp.url) keep working
    unchanged regardless of which fetch path actually served the page."""

    def __init__(self, url, text, status_code=200):
        self.url = url
        self.text = text
        self.status_code = status_code


def _get_context():
    if "context" not in _state:
        from patchright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        _state["playwright"] = pw
        _state["browser"] = browser
        _state["context"] = context
    return _state["context"]


def fetch(url, timeout=45, wait_for_challenge=25):
    """Fetches url via a stealth headless browser, waiting out a Cloudflare
    challenge if one appears. Returns a BrowserResponse, or None on failure.

    Serialized behind a module-level lock: a single shared browser instance
    isn't meant to load many pages truly concurrently across threads, and
    this fallback path is only meant for the minority of URLs the normal
    HTTP client couldn't get through on, so lower throughput here is an
    acceptable trade for reliability.
    """
    with _lock:
        page = None
        try:
            context = _get_context()
            page = context.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")

            deadline = time.time() + wait_for_challenge
            while time.time() < deadline:
                html = page.content()
                if not any(marker in html for marker in _CHALLENGE_MARKERS):
                    return BrowserResponse(url, html)
                time.sleep(1.5)

            # Challenge never cleared within the budget -- return whatever
            # we have (caller treats a challenge page as a failed fetch).
            html = page.content()
            if any(marker in html for marker in _CHALLENGE_MARKERS):
                return None
            return BrowserResponse(url, html)
        except Exception:
            return None
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass


def close():
    """Shuts down the shared browser. Call once at the very end of a
    script's run; best-effort, failures here don't matter."""
    with _lock:
        try:
            if "browser" in _state:
                _state["browser"].close()
            if "playwright" in _state:
                _state["playwright"].stop()
        except Exception:
            pass
        _state.clear()
