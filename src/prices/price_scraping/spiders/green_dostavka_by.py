"""Spider for Green Dostavka (Belarus) -- https://green-dostavka.by/.

"ГРИНрозница" (Green retail) is a Minsk convenience-store chain running its
own online delivery storefront. `curl_cffi impersonate=chrome124` clears
cleanly with HTTP 200 on every path probed -- no anti-bot layer observed
(unlike the sibling Belarusian candidate edostavka.by / Evroopt, which
gates behind a client-side JS cookie challenge that also rate-limits
aggressively; not pursued this wave once green-dostavka.by verified
clean).

The site publishes a full sitemap (`/sitemap.xml` -> one sub-sitemap at
`/sub-sitemaps/sitemap-0.xml`) listing ~19.8k `/product/<slug>-<id>/` URLs
directly -- far more reliable than crawling the 3-level `/catalog/<l1>/<l2>/
<l3>/` category tree (parent category pages only show a partial listing;
e.g. the "molochnye-produkty-syr-yajca" (dairy) parent page shows 106
products total but its own "syry" (cheese) child alone has 60 -- the
category tree undercounts unless walked to full leaf depth). The spider
therefore reads the sitemap and hits each PDP directly.

Each PDP embeds a clean schema.org `Product` JSON-LD block: `sku` (stable
numeric id, also the URL's trailing segment), `name`, `category` (leaf
category name), and `offers.price` / `offers.priceCurrency` (BYN, 2
decimals). No JS rendering needed.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://green-dostavka.by"
_SITEMAP_INDEX = f"{_BASE}/sitemap.xml"

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_SKU_RE = re.compile(r"-(\d+)/?$")
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


class GreenDostavkaBySpider(scrapy.Spider):
    name = "green_dostavka_by"
    allowed_domains = ["green-dostavka.by"]
    currency = "BYN"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={"impersonate": "chrome124"},
        )

    def parse_sitemap_index(self, response):
        for loc in _LOC_RE.findall(response.text):
            yield scrapy.Request(
                loc.strip(),
                callback=self.parse_sitemap,
                meta={"impersonate": "chrome124"},
            )

    def parse_sitemap(self, response):
        n = 0
        for loc in _LOC_RE.findall(response.text):
            loc = loc.strip()
            if "/product/" not in loc:
                continue
            n += 1
            yield scrapy.Request(
                loc,
                callback=self.parse_product,
                meta={"impersonate": "chrome124"},
            )
        logger.info(f"green_dostavka_by: sitemap {response.url} -> {n} product URLs")

    def parse_product(self, response):
        product = None
        for block in _LD_JSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break

        if product is None:
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        sku = product.get("sku")

        if not name or price is None:
            return

        m = _SKU_RE.search(response.url)
        product_id = sku or (m.group(1) if m else None)
        if not product_id:
            return

        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return
        if price_val <= 0:
            return

        name = re.sub(r"\s+", " ", str(name)).strip()

        yield {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": product.get("category"),
            "price": str(price_val),
            "currency": offers.get("priceCurrency") or self.currency,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
