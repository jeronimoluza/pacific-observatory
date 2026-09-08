"""
Spider for e-baa (Kosovo) - https://e-baa.com/

Next.js storefront, server-rendered PDPs (name/price present in raw HTML,
no JS execution needed -- Tier 1A). Category-page pagination (`?page=N`)
does not work (page 2 returns the same 24 items as page 1), so this walks
the site's own sitemap instead: https://panel.e-baa.com/sitemaps/products.xml
lists every product slug under /product/<slug> on the CMS origin
(panel.e-baa.com); the public storefront serves the same slug at
https://e-baa.com/products/<slug> (confirmed live 2026-09-06, 200 with
real EUR price text).

Verified live 2026-09-06 with curl_cffi impersonate=chrome124: sitemap has
685 <loc> entries; sample PDP (air-cooler-timit-w-ac927-r-0625-2838336)
returns EUR 99.00 in span.text-lg.font-semibold.text-primary; a second PDP
(tv-sunny-65-qled...) returns EUR 499.00 via the same selector, with no
collision against the unrelated-products-carousel price spans on the same
page (those use a different class + reversed "279.00€" digit-then-symbol
format).

Catalogue is broad non-food: appliances (fridges, washers, TVs, phones),
small kitchen appliances, furniture, garden/pool, toys, personal care --
[RECLASSIFIED in pass 3 to ACCEPT non-food; AI_NOTES calling it "homeware,
garden, cosmetics, toys" undersold it -- TVs/phones/large-appliances are
also on the shelf]. channel: dept-store (broad, non-grocery-led).
coicop_codes unset -- wide catalogue, classifier assigns leaves per product.

product_id is the trailing numeric SKU segment of the URL slug (e.g.
"2838336"), extracted in code rather than via CSS.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://panel.e-baa.com/sitemaps/products.xml"
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_SLUG_RE = re.compile(r"/product/([^/<\s]+)")
_ID_RE = re.compile(r"-(\d+)$")


class EbaaKsSpider(scrapy.Spider):
    name = "ebaa_ks"
    allowed_domains = ["e-baa.com", "panel.e-baa.com"]
    currency = "EUR"
    language = "sq"

    SELECTORS = get_selectors("ebaa_ks")

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
    }

    async def start(self):
        yield scrapy.Request(SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        logger.info(f"{self.name} sitemap={response.url} urls={len(locs)}")
        for loc in locs:
            m = _SLUG_RE.search(loc)
            if not m:
                continue
            slug = m.group(1)
            url = f"https://e-baa.com/products/{slug}"
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS.get("category", []), method="get"
        )
        id_match = _ID_RE.search(response.url)
        product_id = id_match.group(1) if id_match else None

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")
