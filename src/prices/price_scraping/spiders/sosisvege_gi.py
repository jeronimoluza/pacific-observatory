"""
Sosi's Vege (Gibraltar) -- https://www.sosisvege.com/.

Gibraltar's FIRST price source of any kind. A Gibraltar-domiciled greengrocer
importing Moroccan fruit and vegetables, with a real online catalogue:
15 categories, ~190 SKUs, heavily food-weighted (vegetables 45, main groceries
48, fruit 40, nuts 15, spices 13, plus bread, drinks, olives, oil and honey).

Confirmed Gibraltar-domiciled, not a Spanish shop delivering across the
frontier -- the site's own schema.org PostalAddress reads
{"streetAddress": "18 Parliament lane", "addressLocality": "Gibraltar",
 "postalCode": "GX11 1AA", "addressCountry": "GI"}.

Why Gibraltar previously read as unsourceable: the 2026-09-01 ECA inventory
found only Eroski (www.eroski.gi), which is a genuine reCAPTCHA Enterprise
wall -- verified across three TLS profiles AND a headless Playwright render,
so it is a real block, not a curl-TLS false negative. That verdict stands.
Sosi's Vege was never probed. Also checked this pass and rejected:
  - order.ramsons.gi  -> "Web Ordering Coming Soon"; Ramsons (Gibraltar
    supermarket since 1975) is app-only, iOS/Android, no web catalogue.
  - nomnoms.gi        -> restaurant food-ordering aggregator, not a grocer.

Platform is site123 ("s123-*" classes, images on cdn-files-a.com). Tier 1A --
server-rendered, no anti-bot, no JS needed.

    >>> DO NOT ADD PAGINATION <<<
    Category pages render their entire product set at once (main-groceries
    returns all 48 in one response). The site accepts a `?page=` parameter but
    IGNORES it: `?page=2` re-serves page 1 byte-for-byte. Following it would
    loop forever re-yielding the same products, which is the same
    re-served-last-page trap that produced 92,688 duplicate drops on the
    Magento base. Categories are fetched once each.

Product cards and category tiles share the same markup; tiles are told apart
by the `?c=<hex>` query on their href and skipped.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sosisvege.com"
START_URL = f"{BASE_URL}/"

_CATEGORY_RE = re.compile(r"^/shopping-categories/[a-z0-9\-]+$")


class SosisvegeGiSpider(scrapy.Spider):
    name = "sosisvege_gi"
    allowed_domains = ["sosisvege.com", "www.sosisvege.com"]
    currency = "GIP"
    language = "en"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse_home, dont_filter=True)

    def parse_home(self, response):
        seen = set()
        for href in response.css("a::attr(href)").getall():
            path = urljoin(BASE_URL, href)[len(BASE_URL) :].split("?")[0].split("#")[0]
            if not _CATEGORY_RE.match(path) or path in seen:
                continue
            seen.add(path)
            yield scrapy.Request(
                BASE_URL + path,
                callback=self.parse_category,
                meta={"category": path.rsplit("/", 1)[-1].replace("-", " ")},
                dont_filter=True,
            )
        logger.info(f"{self.name}: discovered {len(seen)} categories")

    def parse_category(self, response):
        category = response.meta["category"]
        found = 0
        for card in response.css("div.detailPart"):
            href = card.css("h4.product-title a::attr(href)").get() or ""
            name = (card.css("h4.product-title a::text").get() or "").strip()
            # A "?c=<hex>" href is a category tile, not a product.
            if not name or not href or "?c=" in href:
                continue
            price = card.css('span[data-type="price"]::text').get()
            if not price:
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            found += 1
            yield {
                "product_id": href.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": urljoin(BASE_URL, href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"{self.name}: {category} yielded={found}")
