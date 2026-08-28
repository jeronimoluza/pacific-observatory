"""
Spider for Cjenoteka (Croatia) — https://cjenoteka.hr.

A price-comparison aggregator (backed by the priceteka.com API, not a
retailer itself — complements the already-onboarded CroCart aggregator,
which covers a different fixed 23-commodity comparison set from a
different 5-chain source list). The homepage is Next.js SSR: the raw
HTML carries a `__NEXT_DATA__` JSON blob with `featured`/`bestseller`/
`popular` product lists, each product priced across multiple real
retailers (dm, Bipa, Konzum hipermarket/supermarket, Kaufland, Plodine
hipermarket/supermarket, ...). Re-verified live 2026-08-06: GET
https://cjenoteka.hr/ -> HTTP 200, 671KB, `__NEXT_DATA__` present.
Sample: 'DUKAT Lagano jutro trajno mlijeko bez laktoze 1,5%mm 1l' —
1.99 EUR at Konzum, 1.73 EUR at Kaufland, 1.69 EUR at Studenac. No
search/browse API route for the wider catalogue was found within
budget (JS bundle only exposes the generic Next.js framework chunks,
not a page-data fetch endpoint), so coverage is the ~18 curated
homepage products x up to ~16 retailers each — narrow, but every price
point is real and retailer-attributed.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://cjenoteka.hr/"
_NEXT_DATA_RE = re.compile(
    r'__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


class CjenotekaHrSpider(scrapy.Spider):
    name = "cjenoteka_hr"
    allowed_domains = ["cjenoteka.hr"]
    currency = "EUR"
    language = "hr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse_page)

    def parse_page(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("cjenoteka_hr: __NEXT_DATA__ not found")
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning("cjenoteka_hr: __NEXT_DATA__ not valid JSON")
            return
        props = (data.get("props") or {}).get("pageProps") or {}
        products: list[dict] = []
        for key in ("featured", "bestseller", "popular"):
            products.extend(props.get(key) or [])
        seen: set[str] = set()
        for p in products:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            name = html.unescape((p.get("name") or "").strip())
            if not name:
                continue
            for price_entry in p.get("prices") or []:
                price = price_entry.get("current_price")
                shop = price_entry.get("shop")
                if price is None or not shop:
                    continue
                yield {
                    "product_id": f"{pid}:{shop}",
                    "product_name": name[:500],
                    "category": shop,
                    "price": str(price),
                    "currency": self.currency,
                    "available": bool(price_entry.get("in_stock", True)),
                    "url": f"{_URL}p/{p.get('slug', pid)}#{shop}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
