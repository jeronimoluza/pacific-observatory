"""
Spider for Jumbo Souq (Qatar) -- https://jumbosouq.com/. Next.js app-router
SSR electronics/home-appliances/gadgets store. `jumbosouq.com` 307s to
`/en` (locale prefix). robots.txt at https://jumbosouq.com/robots.txt points
at a real product sitemap index (https://jumbosouq.com/sitemap/sitemap.xml
-> sitemap-product-en-1.xml + sitemap-product-en-2.xml, 5000 + ~4000 <loc>
entries, ~9k products). Each PDP embeds a schema.org Product JSON-LD block
server-side with a real Offer (QAR price, priceCurrency, availability, sku),
confirmed live 2026-08-17 on /en/apple-iphone-15-plus-512gb-blue -> QAR
4449.00, InStock, sku "603001000001366", description explicitly "online in
Qatar from Jumbo Souq".

Re-verified live 2026-08-17: GET https://jumbosouq.com/sitemap/sitemap.xml
-> 200, 2 English product sitemaps (+2 Arabic, not used). GET one PDP -> 200,
506KB, real QAR price in ld+json Offer.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAPS = [
    "https://jumbosouq.com/sitemap/sitemap-product-en-1.xml",
    "https://jumbosouq.com/sitemap/sitemap-product-en-2.xml",
]
# ~9k products across both sitemaps (5000 + 4022 <loc> entries, confirmed
# live 2026-08-17); cap set above the full catalog so the run is bounded by
# the actual URL count, not an artificial ceiling. At the ishtari_lb bench
# rate (~7.35 req/s @ CONCURRENT_REQUESTS_PER_DOMAIN=16, comparable PDP
# payload/site stack) the full catalog is ~20min, inside the 25min budget.
_MAX_PRODUCTS = 9500
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class JumbosouqQaSpider(scrapy.Spider):
    name = "jumbosouq_qa"
    allowed_domains = ["jumbosouq.com"]
    currency = "QAR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scheduled = 0

    async def start(self):
        for sm in _SITEMAPS:
            yield scrapy.Request(sm, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        for url in urls:
            if self._scheduled >= _MAX_PRODUCTS:
                return
            self._scheduled += 1
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break
        if not product:
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        yield {
            "product_id": str(product.get("sku") or response.url.rsplit("/", 1)[-1]),
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(offers.get("availability", "")).endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
