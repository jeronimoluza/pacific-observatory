"""
Spider for Carrefour Taiwan — now operated by Uni-Prosperity under the rebrand
to online.uni-prosperity.com.tw (the old online.carrefour.com.tw 301s here).

The site is SalesForce Commerce Cloud (Demandware). Robots.txt exposes a
sitemap_index.xml that points to 75 product sub-sitemaps (~5,000 URLs each in
alternating /zh/ + /en/ variants — ~160,000 unique Chinese product pages).

Rather than fetching the 830 KB PDP HTML for each product, we hit the SFCC
Product-Variation JSON endpoint (~57 KB) keyed by SKU. The endpoint exposes
productName, price.sales.value/currency, brand, mainCategory, EAN, etc.

scrapy-impersonate with safari17_0 (Chrome TLS gets blocked, JS-rendering not
needed). Same anti-bot pattern as Rakuten and 11st.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_INDEX = "https://online.uni-prosperity.com.tw/sitemap_index.xml"
PV_API = (
    "https://online.uni-prosperity.com.tw"
    "/on/demandware.store/Sites-Uniprosperity-Site/zh_TW/Product-Variation?pid={sku}"
)
# Extract SKU = last URL segment before `.html`. SKUs are mixed-case alphanumeric.
SKU_RE = re.compile(r"/([A-Za-z0-9]+)\.html$")


class CarrefourTwSpider(scrapy.Spider):
    name = "carrefour_tw"
    allowed_domains = ["online.uni-prosperity.com.tw"]
    currency = "TWD"
    language = "zh"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 32,
        "CONCURRENT_REQUESTS": 64,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        # Global settings enable AutoThrottle with TARGET_CONCURRENCY=4, which
        # capped the previous full run at ~170 items/min despite the higher
        # CONCURRENT_REQUESTS_PER_DOMAIN. Site returns zero 429s — disable.
        "AUTOTHROTTLE_ENABLED": False,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_skus: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(
            SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
            errback=self.errback,
        )

    def parse_sitemap_index(self, response):
        sub_sitemaps = response.xpath("//*[local-name()='loc']/text()").getall()
        product_sms = [s for s in sub_sitemaps if "-product.xml" in s]
        logger.info(
            f"sitemap_index: {len(sub_sitemaps)} sub-sitemaps "
            f"({len(product_sms)} product sub-sitemaps)"
        )
        for sm_url in product_sms:
            yield scrapy.Request(
                sm_url,
                callback=self.parse_product_sitemap,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
                errback=self.errback,
            )

    def parse_product_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        skus: list[str] = []
        for u in urls:
            if "/zh/" not in u:
                continue
            m = SKU_RE.search(u)
            if not m:
                continue
            sku = m.group(1)
            if sku in self.scraped_skus:
                continue
            self.scraped_skus.add(sku)
            skus.append(sku)
        logger.info(
            f"{response.url.rsplit('/', 1)[-1]}: {len(urls)} urls, queued {len(skus)} skus"
        )
        for sku in skus:
            yield scrapy.Request(
                PV_API.format(sku=sku),
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "sku": sku},
                errback=self.errback,
                headers={"Accept": "application/json"},
            )

    def parse_product(self, response):
        sku = response.meta["sku"]
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning(f"sku={sku}: non-JSON response")
            return
        p = data.get("product") or {}
        sales = ((p.get("price") or {}).get("sales") or {})
        price = sales.get("value")
        if price is None:
            return
        name = p.get("productName") or p.get("oriProductName")
        if not name:
            return
        brand = p.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        availability = p.get("availability") or {}
        if isinstance(availability, dict):
            availability = availability.get("messages", [None])[0] if availability.get("messages") else None
        yield {
            "product_id": str(p.get("id") or sku),
            "product_name": name.strip()[:500],
            "brand": brand,
            "category": p.get("mainCategory") or p.get("topLevelCategory"),
            "price": str(price),
            "currency": sales.get("currency") or self.currency,
            "ean": p.get("EAN"),
            "available": p.get("available"),
            "url": p.get("productUrl") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
