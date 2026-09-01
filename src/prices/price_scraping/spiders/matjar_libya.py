"""
Spider for matjar-libya.com ("Matjar Libya" / متجر ليبيا) -- Libya general
dropship marketplace. Next.js storefront, server-rendered.

Listing pages: GET https://www.matjar-libya.com/products?page=<n>
Verified live 2026-09-01: page=1..5 each return a distinct slice of PDP
links (`href="/products/<slug>"`); page=6+ returns zero product links --
clean stop condition. Total confirmed 112 unique PDP urls across pages
1-5, matching the page's own embedded JSON-LD
`{"@type":"ItemList","numberOfItems":112}` exactly -- deterministic,
non-overlapping pagination (not the "flat re-served last page" failure
mode).

Each PDP embeds a clean schema.org Product JSON-LD block:
`{"@type":"Product","name":...,"sku":...,"category":...,
"offers":{"priceCurrency":"LYD","price":"199.00",...}}`. `price` is
already a plain decimal string in whole LYD (e.g. "199.00") -- no
thousands-separator or minor-unit ambiguity; the page's own *display*
text uses a comma as decimal separator ("199,00 د.ل.") which would be
easy to misread as a thousands separator, so this spider deliberately
reads the JSON-LD `price` field instead of the rendered text.

Catalog is general dropship goods (home gadgets, beauty/skincare, baby
toys, kitchen gadgets, health devices) -- workbook note confirmed live:
"anti-theft bags, camera detectors, hair oil" is representative; the
"matbakh-libya" (kitchen) category is kitchen GADGETS (vegetable cutters,
cutlery sets, food-storage boxes), not food ingredients. channel:
marketplace, does NOT count toward the food total.

Locality: prices are LYD, delivery explicitly to Tripoli/Benghazi/Misrata
"and all cities" (site's own About page + schema.org Organization
areaServed=Libya) -- passes rule 8 despite the storefront's contact
WhatsApp/phone number carrying a +33 (France) prefix, which is common for
externally-operated dropship-to-Libya storefronts and is noted here for
transparency, not treated as a locality failure.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.matjar-libya.com"
_LISTING = _BASE + "/products?page={}"
_MAX_PAGES = 20  # safety cap; live catalog stops at page 5 (112 products)

_PDP_HREF_RE = re.compile(r'href="(/products/[a-zA-Z0-9\-]+)"')


class MatjarLibyaSpider(scrapy.Spider):
    name = "matjar_libya"
    allowed_domains = ["matjar-libya.com", "www.matjar-libya.com"]
    currency = "LYD"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _LISTING.format(1), callback=self.parse_listing, meta={"page": 1}
        )

    def parse_listing(self, response):
        page = response.meta["page"]
        hrefs = sorted(set(_PDP_HREF_RE.findall(response.text)))
        logger.info(f"{self.name}: listing page {page}, {len(hrefs)} product links")
        if not hrefs:
            return
        for href in hrefs:
            yield scrapy.Request(_BASE + href, callback=self.parse_pdp)
        if page < _MAX_PAGES:
            yield scrapy.Request(
                _LISTING.format(page + 1),
                callback=self.parse_listing,
                meta={"page": page + 1},
            )

    def parse_pdp(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script)
            except ValueError:
                continue
            blocks = data if isinstance(data, list) else [data]
            for block in blocks:
                if block.get("@type") != "Product":
                    continue
                name = block.get("name")
                sku = block.get("sku")
                category = block.get("category")
                offers = block.get("offers") or {}
                price = offers.get("price")
                currency = offers.get("priceCurrency") or self.currency
                if not name or price in (None, ""):
                    continue
                available = offers.get("availability", "")
                yield {
                    "product_id": str(sku)
                    if sku
                    else response.url.rstrip("/").rsplit("/", 1)[-1],
                    "product_name": str(name).strip(),
                    "category": category,
                    "price": str(price),
                    "currency": currency,
                    "available": "InStock" in available if available else True,
                    "url": response.url,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
                return
        logger.warning(f"{self.name}: no Product JSON-LD found on {response.url}")
