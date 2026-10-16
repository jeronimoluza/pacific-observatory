"""Polite Google News client: one global rate limiter, one thread, loud failures.

Every request to Google (RSS search, and the two requests of a link decode) waits
for the same limiter, DELAY seconds apart with jitter. A 429 or CAPTCHA page backs
off once (BACKOFF_S, then doubled delay) and a second one raises ``Blocked``. A
200 that is not the RSS shape we parse raises ``FormatChanged``.
"""

from __future__ import annotations

import random
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

RSS_SEARCH = "https://news.google.com/rss/search"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
DELAY = (3.0, 5.0)
BACKOFF_S = 300
MAX_BLOCKS = 2


class Blocked(RuntimeError):
    """Google answered 429 or a CAPTCHA page twice: stop the run."""


class FormatChanged(RuntimeError):
    """Google answered 200 with something that is not the RSS we parse."""


@dataclass
class Item:
    title: str
    link: str
    pub: datetime
    source_host: str


def _blocked(resp: requests.Response) -> bool:
    return (
        resp.status_code == 429
        or "/sorry/" in resp.url
        or b"unusual traffic" in resp.content[:5000]
    )


def parse_rss(content: bytes) -> list[Item]:
    """Items of a Google News RSS search; raise FormatChanged if the shape moved."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise FormatChanged(f"RSS does not parse: {e}; starts {content[:120]!r}")
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise FormatChanged(f"no <rss><channel>: root <{root.tag}>")
    items = []
    for it in channel.iter("item"):
        link, pub, src = it.findtext("link"), it.findtext("pubDate"), it.find("source")
        if not link or not pub or src is None or not src.get("url"):
            raise FormatChanged(
                "item without link, pubDate or <source url>: "
                + ET.tostring(it, encoding="unicode")[:300]
            )
        try:
            ts = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except (TypeError, ValueError):
            raise FormatChanged(f"pubDate does not parse: {pub!r}")
        host = urlparse(src.get("url")).netloc.lower().removeprefix("www.")
        items.append(Item(it.findtext("title") or "", link, ts, host))
    return items


class GoogleClient:
    def __init__(self, delay: tuple[float, float] = DELAY, backoff_s: int = BACKOFF_S):
        self.delay = delay
        self.backoff_s = backoff_s
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"}
        )
        self.requests = 0
        self.blocks = 0
        self._last = 0.0
        self._decoder = None

    def _wait(self) -> None:
        left = self._last + random.uniform(*self.delay) - time.monotonic()
        if left > 0:
            time.sleep(left)

    def _on_block(self, what: str) -> None:
        self.blocks += 1
        if self.blocks >= MAX_BLOCKS:
            raise Blocked(f"blocked {self.blocks}x by Google ({what}); stopping")
        print(f"  BLOCK ({what}); backing off {self.backoff_s}s", flush=True)
        time.sleep(self.backoff_s)
        self.delay = (self.delay[0] * 2, self.delay[1] * 2)

    def search(self, query: str, hl: str, gl: str) -> list[Item]:
        params = {"q": query, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl}"}
        while True:
            self._wait()
            self.requests += 1
            try:
                resp = self.session.get(RSS_SEARCH, params=params, timeout=30)
            finally:
                self._last = time.monotonic()
            if _blocked(resp):
                self._on_block(f"HTTP {resp.status_code} {resp.url[:80]}")
                continue
            resp.raise_for_status()
            if urlparse(resp.url).netloc != "news.google.com":
                raise FormatChanged(f"redirected to {resp.url[:120]}")
            return parse_rss(resp.content)

    def decode(self, link: str) -> str | None:
        """Article URL behind a news.google.com link: 1 GET + 1 batchexecute POST.

        Needs ``googlenewsdecoder`` (not a project dependency; see the report).
        """
        if self._decoder is None:
            try:
                from googlenewsdecoder import GoogleDecoder
            except ImportError as e:
                raise SystemExit(
                    "--sample needs googlenewsdecoder==0.2.1 and selectolax<1.0 "
                    f"(not installed: {e})"
                )
            self._decoder = GoogleDecoder(user_agent=UA, timeout=20)
        self._wait()
        self.requests += 2
        try:
            res = self._decoder.decode_google_news_url(link)
        finally:
            self._last = time.monotonic()
        msg = str(res.get("message") or "")
        if any(s in msg.lower() for s in ("429", "sorry", "unusual traffic")):
            self._on_block(f"decode: {msg[:80]}")
            return None
        return res.get("decoded_url") if res.get("success") else None
