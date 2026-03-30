"""HTTP session helpers with throttling, retries, and proxy support."""

from __future__ import annotations

import random
import threading
import time

import requests
from rich.console import Console

console = Console()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

_IMAGE_SIGNATURES = (
    b"\xff\xd8\xff",
    b"\x89PNG\r\n\x1a\n",
    b"GIF87a",
    b"GIF89a",
    b"RIFF",
)


class SmartSession:
    def __init__(self, proxy=None, min_delay=0.3, max_delay=1.5):
        self.proxy = proxy
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.request_count = 0
        self._next_request_time = 0.0
        self._state_lock = threading.Lock()
        self._thread_local = threading.local()

    def _build_session(self):
        session = requests.Session()
        if self.proxy:
            session.proxies = {"http": self.proxy, "https": self.proxy}
        session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })
        self._rotate_ua(session)
        return session

    def _get_session(self):
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = self._build_session()
            self._thread_local.session = session
        return session

    def _rotate_ua(self, session=None):
        session = session or self._get_session()
        session.headers["User-Agent"] = random.choice(USER_AGENTS)

    def _reserve_request_slot(self):
        with self._state_lock:
            now = time.time()
            slot_time = max(now, self._next_request_time)
            wait = max(0.0, slot_time - now)
            base_delay = random.uniform(self.min_delay, self.max_delay)
            if self.request_count > 0 and self.request_count % 30 == 0:
                base_delay += random.uniform(2.0, 5.0)
                rotate = True
            else:
                rotate = False
            self._next_request_time = slot_time + base_delay
            return wait, rotate

    def _mark_request_complete(self):
        with self._state_lock:
            self.request_count += 1

    @staticmethod
    def _retry_delay(attempt: int, base: float, spread: float = 0.0) -> float:
        return (2**attempt) * base + (random.uniform(0, spread) if spread else 0.0)

    @staticmethod
    def _should_retry_status(status_code: int) -> bool:
        return status_code == 429 or status_code == 403 or 500 <= status_code < 600

    def get(self, url, max_retries=3, **kwargs):
        kwargs.setdefault("timeout", 30)
        last_err = None

        for attempt in range(max_retries):
            wait, rotate = self._reserve_request_slot()
            if wait > 0:
                time.sleep(wait)

            session = self._get_session()
            if rotate:
                self._rotate_ua(session)

            try:
                resp = session.get(url, **kwargs)
                self._mark_request_complete()

                if resp.status_code == 429:
                    wait = self._retry_delay(attempt, 5, 3)
                    console.print(f"  [yellow]Rate limited 429, waiting {wait:.0f}s...[/]")
                    resp.close()
                    time.sleep(wait)
                    self._rotate_ua(session)
                    continue
                if resp.status_code == 403:
                    wait = self._retry_delay(attempt, 3, 2)
                    console.print(f"  [yellow]Forbidden 403, rotating UA, waiting {wait:.0f}s...[/]")
                    resp.close()
                    time.sleep(wait)
                    self._rotate_ua(session)
                    session.cookies.clear()
                    continue
                if self._should_retry_status(resp.status_code):
                    wait = self._retry_delay(attempt, 2)
                    console.print(f"  [yellow]HTTP {resp.status_code}, retry {attempt + 1}/{max_retries} in {wait:.0f}s...[/]")
                    resp.close()
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_err = e
                wait = self._retry_delay(attempt, 2, 1.5)
                console.print(f"  [yellow]Connection error, retry {attempt + 1}/{max_retries} in {wait:.0f}s...[/]")
                time.sleep(wait)
            except requests.exceptions.HTTPError as e:
                last_err = e
                raise

        raise requests.exceptions.ConnectionError(f"Failed after {max_retries} retries: {last_err}")

    @staticmethod
    def _looks_like_image(content: bytes) -> bool:
        if not content:
            return False
        if content.startswith(_IMAGE_SIGNATURES[0]) or content.startswith(_IMAGE_SIGNATURES[1]):
            return True
        if content.startswith(_IMAGE_SIGNATURES[2]) or content.startswith(_IMAGE_SIGNATURES[3]):
            return True
        if content.startswith(_IMAGE_SIGNATURES[4]):
            return len(content) >= 12 and content[8:12] == b"WEBP"
        return False

    def get_image(self, url, referer, max_retries=3):
        headers = {"Referer": referer, "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"}
        try:
            resp = self.get(url, max_retries=max_retries, headers=headers)
            content_type = (resp.headers.get("Content-Type") or "").lower()
            data = resp.content
            if content_type and not content_type.startswith("image/"):
                if not self._looks_like_image(data):
                    console.print(f"  [yellow]Skipping non-image response ({content_type or 'unknown'}) from {url}[/]")
                    return None
            if not self._looks_like_image(data):
                console.print(f"  [yellow]Skipping invalid image payload from {url}[/]")
                return None
            return data
        except Exception as exc:
            console.print(f"  [yellow]Image download failed for {url}: {exc}[/]")
            return None

    def get_json(self, url, max_retries=3, **kwargs):
        kwargs.setdefault("timeout", 30)
        resp = self.get(url, max_retries=max_retries, **kwargs)
        return resp.json()

