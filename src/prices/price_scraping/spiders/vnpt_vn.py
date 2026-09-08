"""Spider for VNPT (https://vnpt.vn/) -- Vietnam's state-owned telecom
carrier. Mobile plan tariffs (COICOP 08.1.0 telephone and internet
services).

Contrary to a prior inventory note calling VNPT's plan pages "SPA-loaded",
``/di-dong`` (mobile) is plainly server-rendered -- confirmed 2026-09-06
with curl_cffi impersonate=chrome124, no WAF encountered, no Playwright
needed. All plan cards across every tab (prepaid "tratruoc", postpaid
"trasau", SIM kits, data-only, value-added services, "rx") are rendered
into the same HTML response; the tabs are CSS-toggled client-side, not
separate fetches, so a single page fetch yields all ~15 plans.

Card DOM: ``div.card.card-item`` with a ``h3.head a.title`` (plan code,
e.g. "SODA155") and a ``div.desc p.tag strong`` price string (e.g.
"155.000 đ/30 ngày"). Price is VND with dot-grouped thousands; parsed by
stripping non-digits before the currency symbol.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_PRICE_RE = re.compile(r"([\d.]+)\s*đ")

_LANDING_URL = "https://vnpt.vn/di-dong"


class VnptVnSpider(scrapy.Spider):
    name = "vnpt_vn"
    allowed_domains = ["vnpt.vn"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _LANDING_URL,
            callback=self.parse,
            meta={"impersonate": "chrome124"},
        )

    def parse(self, response):
        cards = response.css("div.card.card-item")
        emitted = 0
        for card in cards:
            item = self._item(card, response.url)
            if item is not None:
                emitted += 1
                yield item
        self.logger.info("vnpt_vn: cards=%d emitted=%d", len(cards), emitted)

    def _item(self, card, base_url: str) -> dict | None:
        title = card.css("h3.head a.title::text").get()
        href = card.css("h3.head a.title::attr(href)").get()
        price_text = card.css("div.desc p.tag strong::text").get()
        if not (title and price_text):
            return None
        m = _PRICE_RE.search(price_text)
        if not m:
            return None
        price = float(m.group(1).replace(".", ""))
        if price <= 0:
            return None
        url = urljoin(base_url, href) if href else base_url
        return {
            "product_id": title.strip(),
            "product_name": title.strip(),
            "category": "mobile-plan",
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
