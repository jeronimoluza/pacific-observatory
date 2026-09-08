"""
Spider for Carrefour Romania (Hypermarket) -- https://carrefour.ro/.

Shard/AI_NOTES round-1 mislabeled this "VTEX" -- wrong platform. robots.txt
explicitly names "Disable Magento Standard" (`/catalog/product`,
`/new_catalog/product`) and the raw homepage HTML contains "Magento" but
no "VTEX" string. The standard VTEX `catalog_system` REST endpoints all
404 with the site's own Next.js 404 body (verified live 2026-09-06:
`/api/catalog_system/pub/category/tree/3` -> 404), and the Magento
`/graphql` endpoint is Cloudflare-blocked ("Request forbidden by
administrative rules", 403 on all curl_cffi profiles) -- so this is a
headless Magento backend behind a custom Next.js storefront, with GraphQL
walled off entirely.

Bypasses both APIs by walking https://carrefour.ro/pub/sitemap/sitemap.xml
-> sitemap_002.xml, which lists ~38,630 canonical PDP urls under
`/produse/<slug>-<catId>-<sku>/`. Each PDP server-renders a
`<script type="application/ld+json">` `Product` block with real price/
currency/availability (verified live: sku 14524989 "Ciocolata Ragusa For
Friends cu lapte si alune 132g" RON 44.99) plus a microdata
`BreadcrumbList` (`li[itemprop="itemListElement"] span[itemprop="name"]`)
for category. No Playwright needed -- both are present in the raw HTML.

Some SKUs (mostly apparel/appliances, e.g. sku 63514982) carry
`"price": 0` in JSON-LD -- these are dropped rather than shipped as a
zero price.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://carrefour.ro"
_SITEMAP_INDEX = f"{_BASE}/pub/sitemap/sitemap.xml"
_PRODUCT_URL_RE = re.compile(r"<loc>(https://carrefour\.ro/produse/[^<]+)</loc>")
_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">\s*(\{.*?"@type":\s*"Product".*?\})\s*</script>',
    re.DOTALL,
)
MAX_PRODUCTS = 6000  # safety cap; full sitemap is ~38,630 across all departments


class CarrefourRoSpider(scrapy.Spider):
    name = "carrefour_ro"
    allowed_domains = ["carrefour.ro"]
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
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_index)

    def parse_index(self, response):
        for loc in re.findall(r"<loc>([^<]+)</loc>", response.text):
            if loc.endswith(".xml"):
                yield scrapy.Request(loc, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _PRODUCT_URL_RE.findall(response.text)
        if not urls:
            return
        logger.info(f"carrefour_ro: {response.url} -> {len(urls)} product urls")
        for url in urls[:MAX_PRODUCTS]:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        m = _JSONLD_RE.search(response.text)
        if not m:
            logger.warning(f"carrefour_ro: no JSON-LD Product on {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except (ValueError, TypeError):
            return
        offer = data.get("offers") or {}
        price = offer.get("price")
        if price is None or price == 0:
            return
        crumbs = response.css(
            'li[itemprop="itemListElement"] span[itemprop="name"]::text'
        ).getall()
        category = " > ".join(c.strip() for c in crumbs[1:] if c.strip()) or None

        yield {
            "product_id": data.get("sku"),
            "product_name": str(data.get("name") or "").strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offer.get("priceCurrency", self.currency),
            "available": "instock" in str(offer.get("availability") or "").lower(),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
