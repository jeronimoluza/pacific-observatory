"""
Spider for Al Meera Oman - www.almeera.om

Al Meera (Qatari-origin grocery chain) runs its Oman storefront on a
white-label "Blink"/eatmubarak.pk ordering platform (Next.js, restId 55355,
`com.blink.almeera` app package). Category listings are client-rendered,
but every PDP is server-rendered with a full schema.org Product JSON-LD
block: name, offers.price, offers.priceCurrency, offers.availability. A
`product:retailer_item_id` meta tag carries the numeric product id that
also appears as the trailing number in the URL slug.

Seeded off /sitemap.xml -> 11 `sitemap-products/N.xml` files, ~3,000 URLs
each (~30k+ PDPs total). Verified live 2026-08-31: e.g.
/product/kelloggs-coco-pops-balls-225gr-1508711 -> "Kelloggs Coco Pops
Balls 225Gr" OMR 1.110 (schema.org offers.price, matches the
product:price:amount meta tag); /product/al-ameer-prawn-masala-300-gm-2223185
-> OMR 0.975. Sampled sitemap URLs across files 1/3/6 are overwhelmingly
grocery (snacks, canned/frozen food, spices, dairy, baby food) with a
minority of household/small-appliance SKUs typical of a hypermarket
banner -- channel: hypermarket. No category field in the JSON-LD; PDP URLs
carry no category path segment either, so category is left unset (None).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.almeera.om/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)
_ITEM_ID_RE = re.compile(r'product:retailer_item_id"\s+content="([^"]+)"')


class AlmeeraOmSpider(scrapy.Spider):
    name = "almeera_om"
    allowed_domains = ["almeera.om"]
    currency = "OMR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        product_sitemaps = [
            u for u in _LOC_RE.findall(response.text) if "sitemap-products/" in u
        ]
        logger.info("almeera_om: %d product sitemap files", len(product_sitemaps))
        for url in product_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/product/" in u]
        logger.info("almeera_om: %d product URLs in %s", len(urls), response.url)
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break
        if not product:
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", "0", "0.00", "0.000"):
            return

        availability = offers.get("availability") or ""

        id_m = _ITEM_ID_RE.search(response.text)
        product_id = id_m.group(1) if id_m else response.url

        yield {
            "product_id": product_id,
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "OutOfStock" not in availability,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
