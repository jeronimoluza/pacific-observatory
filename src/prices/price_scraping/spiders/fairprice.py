"""
Spider for FairPrice (Singapore) — Singapore's largest grocery retailer.

The site is Next.js SSR. The public sitemap redirects to an internal subdomain
that is not externally resolvable, so URL discovery instead walks the ten
top-level category pages — each renders ~20 product cards as `<a href="/product/...">`
links directly in HTML. Each product page exposes Schema.org Product JSON-LD
with name, sku, brand, offers.price/priceCurrency/availability.

Replaces the previous scrapy-playwright implementation that hung on the first
category request (logged a single errback, then sat idle for 7+ hours waiting
for nine more Playwright pages that never resolved).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("https://www.fairprice.com.sg/category/fruits-vegetables", "Fruits & Vegetables"),
    ("https://www.fairprice.com.sg/category/meat-seafood", "Meat & Seafood"),
    (
        "https://www.fairprice.com.sg/category/dairy-chilled-eggs",
        "Dairy, Chilled & Eggs",
    ),
    (
        "https://www.fairprice.com.sg/category/rice-noodles-cooking-ingredients",
        "Rice, Noodles & Cooking",
    ),
    ("https://www.fairprice.com.sg/category/beverages", "Beverages"),
    (
        "https://www.fairprice.com.sg/category/snacks-confectionery",
        "Snacks & Confectionery",
    ),
    ("https://www.fairprice.com.sg/category/health-beauty", "Health & Beauty"),
    ("https://www.fairprice.com.sg/category/household", "Household"),
    ("https://www.fairprice.com.sg/category/baby", "Baby"),
    (
        "https://www.fairprice.com.sg/category/breakfast-spreads-canned-food",
        "Breakfast & Canned Food",
    ),
]

PRODUCT_HREF_RE = re.compile(r'href="(/product/[^"]+)"')


class FairPriceSpider(scrapy.Spider):
    name = "fairprice"
    allowed_domains = ["www.fairprice.com.sg"]
    currency = "SGD"
    language = "en"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": False,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_urls: set[str] = set()

    async def start(self):
        for cat_url, cat_name in CATEGORIES:
            yield scrapy.Request(
                cat_url,
                callback=self.parse_category,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "category": cat_name},
                errback=self.errback,
            )

    def parse_category(self, response):
        category = response.meta["category"]
        # Product hrefs are rendered SSR as <a href="/product/<slug>-<id>">.
        paths = set(PRODUCT_HREF_RE.findall(response.text))
        logger.info(f"category={category} discovered {len(paths)} product URLs")
        for path in paths:
            url = response.urljoin(path)
            if url in self.scraped_urls:
                continue
            self.scraped_urls.add(url)
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "category": category},
                errback=self.errback,
            )

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
            return
        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get("price")
        name = product.get("name")
        if not (price and name):
            return
        brand = product.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        yield {
            "product_id": str(product.get("sku") or product.get("@id") or response.url),
            "product_name": str(name).strip()[:500],
            "brand": brand,
            "category": response.meta.get("category"),
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offer.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_product(response):
        # Fairprice ships its JSON-LD script with multiple top-level objects
        # concatenated without an array wrapper, so json.loads bails on the
        # second object. raw_decode walks them one at a time.
        decoder = json.JSONDecoder()
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            text = raw
            while text.strip():
                text = text.lstrip()
                try:
                    obj, end = decoder.raw_decode(text)
                except json.JSONDecodeError:
                    break
                candidates = (
                    obj.get("@graph")
                    if isinstance(obj, dict) and "@graph" in obj
                    else [obj]
                )
                for c in candidates:
                    if isinstance(c, dict) and c.get("@type") == "Product":
                        return c
                text = text[end:]
        return None

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
