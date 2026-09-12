"""
Shared base for sooqnaa.com-hosted Syrian storefronts.

sooqnaa.com is a Syrian storefront host: each merchant gets
`<store>.sooqnaa.com`, a Next.js App Router site. There is a central API
at api.sooqnaa.com but it is authenticated (401 "No authentication token
provided"), so this spider reads the server-rendered React Server
Component flight payload that the storefront itself embeds -- the same
bytes the page renders from, no browser and no JS execution required.

MEASURED 2026-09-12 (curl_cffi impersonate=chrome124):

    GET https://<store>.sooqnaa.com/ar/products?page=N   -> 200 text/html

    The HTML carries N `self.__next_f.push([1,"<json-escaped chunk>"])`
    calls. Concatenating the JSON-decoded chunks reconstructs the flight
    payload, which contains the page's own product array:

        {"id":"<uuid>","name":"...","slug":"...","subtitle":null,
         "promotional_title":null,"price":550,"discount_price":null,
         "is_on_sale":false,"current_price":550,
         "primary_image":{...},"categories":[...],"is_in_stock":true,
         "has_variants":false,...,"is_digital":false}

    and the store config's own `"currency":"SYP"` (or "USD").

ENUMERABILITY (MEASURED across all four onboarded stores): `?page=N`
serves 24 products per page and page 1 vs page 2 are effectively disjoint
-- the 1-3 shared ids per store are the shared "latest products" strip
that every page renders, not a failure to paginate. The spider therefore
tracks ids it has already emitted and stops when a page contributes zero
NEW ones, rather than trusting a page count.

CURRENCY: taken from the store's own `"currency"` field in the flight
payload, cross-checked against the value each subclass pins (measured
2026-09-12). A mismatch is logged and the payload wins -- the site knows
its own currency and vipstore.sooqnaa.com genuinely prices in USD while
the other three price in SYP.

Page family: listing. The `url` emitted is the PDP permalink
(`https://<store>.sooqnaa.com/ar/products/<slug>`, verified 200) which
this spider never fetches.

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

MAX_PAGES = 40  # safety cap

_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
_PRODUCT_START_RE = re.compile(r'\{"id":"[0-9a-f-]{36}","name":"')
_CURRENCY_RE = re.compile(r'"currency":"([A-Z]{3})"')


def _flight_payload(html_text: str) -> str:
    """Reconstruct the RSC flight payload from its escaped page chunks."""
    parts = []
    for chunk in _CHUNK_RE.findall(html_text):
        try:
            parts.append(json.loads(chunk))
        except ValueError:
            continue
    return "".join(parts)


def _balanced_object(text: str, start: int) -> str | None:
    """Return the complete JSON object beginning at `start`, or None.

    Walks braces while respecting string literals and backslash escapes,
    so nested objects (primary_image, categories) do not truncate it.
    """
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _iter_products(flight: str):
    for m in _PRODUCT_START_RE.finditer(flight):
        raw = _balanced_object(flight, m.start())
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if "current_price" in obj or "price" in obj:
            yield obj


class SooqnaaBaseSpider(scrapy.Spider):
    name = None
    STORE_HOST: str = ""
    currency = "SYP"
    language = "ar"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _page_url(self, page: int) -> str:
        return f"https://{self.STORE_HOST}/ar/products?page={page}"

    async def start(self):
        yield scrapy.Request(
            self._page_url(1),
            callback=self.parse_page,
            meta={"page": 1, "seen": set()},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        seen = response.meta["seen"]

        flight = _flight_payload(response.text)
        if not flight:
            logger.warning(f"{self.name}: no RSC flight payload at {response.url}")
            return

        m = _CURRENCY_RE.search(flight)
        currency = m.group(1) if m else self.currency
        if currency != self.currency:
            logger.warning(
                f"{self.name}: store currency {currency} differs from the "
                f"pinned {self.currency}; using the store's own value"
            )

        new_count = 0
        for p in _iter_products(flight):
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            item = self._item(p, currency)
            if item:
                new_count += 1
                yield item

        logger.info(
            f"{self.name} page={page} new={new_count} total_seen={len(seen)}"
        )

        if new_count > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._page_url(nxt),
                callback=self.parse_page,
                meta={"page": nxt, "seen": seen},
            )

    def _item(self, p: dict, currency: str):
        raw = p.get("current_price")
        if raw is None:
            raw = p.get("price")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None

        name = str(p.get("name") or "").strip()
        if not name:
            return None

        cats = p.get("categories") or []
        category = (
            " > ".join(
                str(c.get("name"))
                for c in cats
                if isinstance(c, dict) and c.get("name")
            )
            or None
        )

        slug = p.get("slug")
        return {
            "product_id": str(p.get("id")),
            "product_name": name[:500],
            "category": category,
            "price": str(value),
            "currency": currency,
            "available": bool(p.get("is_in_stock", True)),
            "url": (
                f"https://{self.STORE_HOST}/ar/products/{slug}" if slug else ""
            ),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
