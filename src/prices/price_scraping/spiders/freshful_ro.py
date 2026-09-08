"""
Spider for Freshful by eMAG (Romania) -- https://www.freshful.ro/.

Next.js storefront. `robots.txt` names a `/api/v2/shop` API family but a
Playwright network trace on a PDP shows no client-side fetch for the
product itself -- the entire product record (name, price, currency,
breadcrumbs, availability) is already embedded server-side in the page's
React-Query dehydrated state (`__NEXT_DATA__` ->
`props.pageProps.dehydratedState.queries[0].state.data`, queryKey
`["product", "<slug>"]`). No separate API call needed; plain HTML GET is
enough.

Confirmed live 2026-09-06: PDP
`/p/100075626-soligrano-mix-clatite-din-mei-cu-afine-fara-gluten-71g` ->
200, `data.price` 10.91, `data.currency` "Lei" (mapped to ISO RON --
`currencyCode` field also present but was null on this SKU, "Lei" is the
reliable one), `data.code` "100075626", `data.name` "Mix clătite din mei
cu afine fără gluten 71g", `data.breadcrumbs` gives the full category
path (last entry is the product itself, dropped).

Walks `sitemap/products.xml` (46,297 PDP urls) rather than crawling
categories -- the sitemap already lists the full catalog directly and
categories would need their own page-render/API discovery pass.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.freshful.ro"
_SITEMAP_URL = f"{_BASE}/sitemap/products.xml"
_LOC_RE = re.compile(r"<loc>(https://www\.freshful\.ro/p/[^<]+)</loc>")
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
MAX_PRODUCTS = 6000  # safety cap; full sitemap is 46,297


class FreshfulRoSpider(scrapy.Spider):
    name = "freshful_ro"
    allowed_domains = ["freshful.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info(f"freshful_ro: sitemap yielded {len(urls)} product urls")
        for url in urls[:MAX_PRODUCTS]:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"freshful_ro: no __NEXT_DATA__ on {response.url}")
            return
        try:
            payload = json.loads(m.group(1))
        except (ValueError, TypeError):
            return
        try:
            queries = payload["props"]["pageProps"]["dehydratedState"]["queries"]
        except (KeyError, TypeError):
            return
        data = None
        for q in queries:
            key = q.get("queryKey") or []
            if key and key[0] == "product":
                data = (q.get("state") or {}).get("data")
                break
        if not isinstance(data, dict):
            return

        price = data.get("price")
        name = (data.get("name") or "").strip()
        if not name or price is None:
            return

        breadcrumbs = data.get("breadcrumbs") or []
        category = (
            " > ".join(b.get("name", "") for b in breadcrumbs[:-1] if b.get("name"))
            or None
        )
        currency_raw = (data.get("currency") or "").strip().lower()
        currency = "RON" if currency_raw in ("lei", "ron") else (
            data.get("currencyCode") or self.currency
        )

        yield {
            "product_id": str(data.get("code") or ""),
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": currency,
            "available": bool(data.get("isAvailable", True)),
            "url": data.get("url") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
