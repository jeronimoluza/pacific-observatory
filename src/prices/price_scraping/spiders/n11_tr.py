"""n11.com -- Turkish general marketplace (COICOP: mixed, marketplace).

Verified live 2026-08-17: curl_cffi impersonate=chrome124/chrome120 clear the
Cloudflare "Attention Required" 403 (bare curl 403s; safari17_0 alone still
gets 403'd on this site specifically). This spider relies on the
project-wide default chrome120 TLS impersonation (RandomBrowserMiddleware +
CompositeDownloadHandler in settings.py already impersonate every request as
chrome120; no per-spider override needed since chrome120 is a verified-clean
profile here).

n11 exposes no discovered category-browse sitemap; the working catalog
surface is the Vue-SSR search endpoint https://n11.com/arama?q=<term>. Each
result page server-renders up to 26 product cards:
  <a href="/urun/<slug>-<id>" class="product-item">
    ... <h2 class="product-item-title">NAME</h2> ...
    <h3 class="price-currency">17.400 TL</h3>

Prices are Turkish-locale formatted (period = thousands separator, comma =
decimal). The <h3 class="price-currency"> is the current/effective price;
a preceding <div class="old-price"> (if present) is the pre-discount price
and is ignored.

Enumerability verified live: /arama?q=telefon&pg=1 vs ...&pg=2 returned 26
distinct product ids each, with only 1 id overlapping (near-total churn).

Walks a fixed list of Turkish category search terms (n11 has no stable
category-id taxonomy reachable without JS) with the ``pg`` query param;
channel is marketplace since n11 mixes first- and third-party sellers with
no reliable per-card seller signal in the server-rendered markup, so
coicop_codes is left unset.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://n11.com"
_SEARCH_TERMS = (
    "telefon",
    "bilgisayar",
    "televizyon",
    "beyaz esya",
    "mutfak",
    "elektrikli supurge",
    "giyim",
    "ayakkabi",
    "kozmetik",
    "kucuk ev aletleri",
    "mobilya",
    "oyuncak",
    "kitap",
    "spor",
    "kisisel bakim",
)

_TILE_RE = re.compile(r'<a href="(/urun/[^"]*-(\d+))" class="product-item"', re.DOTALL)
_TITLE_RE = re.compile(r'<h2 class="product-item-title[^"]*"[^>]*>([^<]+)</h2>')
_PRICE_RE = re.compile(r'<h3 class="price-currency"[^>]*>\s*([\d.,]+)\s*TL\s*</h3>')

MAX_PAGES = 30


def _parse_price(raw: str) -> float | None:
    text = raw.strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


class N11TrSpider(scrapy.Spider):
    name = "n11_tr"
    allowed_domains = ["n11.com"]
    currency = "TRY"
    language = "tr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for term in _SEARCH_TERMS:
            yield scrapy.Request(
                f"{_BASE}/arama?q={term.replace(' ', '+')}&pg=1",
                callback=self.parse_listing,
                meta={"term": term, "page": 1},
            )

    def parse_listing(self, response):
        term = response.meta["term"]
        page = response.meta["page"]

        starts = [m.start() for m in _TILE_RE.finditer(response.text)]
        body = response.text
        scraped_at = datetime.now(timezone.utc).isoformat()

        n = 0
        seen_ids = set()
        for i, m in enumerate(_TILE_RE.finditer(body)):
            end = (
                starts[i + 1] if i + 1 < len(starts) else min(len(body), m.end() + 4000)
            )
            block = body[m.start() : end]

            product_id = m.group(2)
            if product_id in seen_ids:
                continue

            title_m = _TITLE_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not title_m or not price_m:
                continue
            price = _parse_price(price_m.group(1))
            if price is None:
                continue

            seen_ids.add(product_id)
            n += 1
            yield {
                "product_id": product_id,
                "product_name": html.unescape(title_m.group(1)).strip()[:500],
                "category": term,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, m.group(1)),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"n11_tr: term={term} page={page} items={n}")

        if n > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/arama?q={term.replace(' ', '+')}&pg={nxt}",
                callback=self.parse_listing,
                meta={"term": term, "page": nxt},
            )
