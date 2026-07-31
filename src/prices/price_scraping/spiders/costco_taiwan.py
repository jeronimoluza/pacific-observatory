"""
Spider for Costco Taiwan — costco.com.tw.

The site is SAP Commerce Cloud (Spartacus storefront, Angular Universal SSR;
`cx-state`/`siteContext` keys in the embedded `#storefront-state` JSON confirm
this — NOT Salesforce as originally guessed). The `/rest/v2/taiwan/products/
search` OCC-style endpoint requires an authenticated session and returns an
empty product list when hit cold, so we do not use it.

Instead: `sitemap_taiwan_product.xml` lists ~15k PDP URLs
(`.../p/{sku}`). Each PDP is server-rendered and embeds a clean
`<script id="schemaorg_product" type="application/ld+json">` block with
name, sku, price, currency, and URL — reachable with a plain GET + browser
UA, no auth/cookies/JS needed.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP = "https://www.costco.com.tw/sitemap_taiwan_product.xml"
_SCHEMA_RE = re.compile(
    r'<script id="schemaorg_product" type="application/ld\+json">(.*?)</script>',
    re.S,
)
# Category = the path segment right before the product-name segment, e.g.
# ".../Food-Dining/Snacks/Nuts-Jerky/Denroku-.../p/74561" -> "Nuts-Jerky".
_CATEGORY_RE = re.compile(r"/([^/]+)/[^/]+/p/[^/]+$")


class CostcoTaiwanSpider(scrapy.Spider):
    name = "costco_taiwan"
    allowed_domains = ["costco.com.tw"]
    currency = "TWD"
    language = "zh"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        yield scrapy.Request(SITEMAP, callback=self.parse_sitemap, errback=self.errback)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/p/" in u]
        logger.info(f"sitemap: {len(urls)} urls, {len(product_urls)} product urls")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        match = _SCHEMA_RE.search(response.text)
        if not match:
            logger.warning(f"no schemaorg_product block: {response.url}")
            return
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning(f"unparseable schemaorg_product JSON: {response.url}")
            return

        name = data.get("name")
        offers = data.get("offers") or {}
        price = offers.get("price")
        if not name or price is None:
            return

        cat_match = _CATEGORY_RE.search(response.url)
        brand = data.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")

        yield {
            "product_id": str(data.get("sku") or ""),
            "product_name": name.strip(),
            "brand": brand,
            "category": cat_match.group(1).replace("-", " ") if cat_match else None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "url": offers.get("url") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
