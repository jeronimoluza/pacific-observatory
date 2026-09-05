"""
Spider for Carrefour (Taiwan) - https://online.carrefour.com.tw/

Carrefour TW runs Salesforce Commerce Cloud (SFCC / Demandware). Category
listing pages are 700KB+ SPA shells but **product detail pages are server
rendered** with schema.org `Product` JSON-LD that includes name and price.

URL discovery is via the public sitemap index, which fans out to
`sitemap_<N>-product.xml` files (74 shards, ~5K URLs each, ~370K total).

Initial pass crawls the first 2 sitemap shards (~10K products) to keep the
runtime bounded. Increase MAX_SITEMAPS to expand coverage.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://online.carrefour.com.tw/sitemap_index.xml"
_SITEMAP_PRODUCT_RE = re.compile(r"sitemap_\d+-product\.xml")
_LDJSON_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


class CarrefourTwSpider(scrapy.Spider):
    name = "carrefour_tw"
    allowed_domains = ["online.carrefour.com.tw"]
    country = "taiwan"
    currency = "TWD"
    language = "zh-TW"

    # Cap initial coverage; first 2 product sitemaps ≈ 10K URLs.
    # Bump this to grow coverage. None = all shards.
    MAX_SITEMAPS = 2

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 8,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def start_requests(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        sitemap_urls = response.xpath(
            "//*[local-name()='sitemap']/*[local-name()='loc']/text()"
        ).getall()
        product_sitemaps = [u for u in sitemap_urls if _SITEMAP_PRODUCT_RE.search(u)]
        if self.MAX_SITEMAPS:
            product_sitemaps = product_sitemaps[: self.MAX_SITEMAPS]
        logger.info(
            "Found %d product sitemaps (using %d, MAX_SITEMAPS=%s)",
            len(sitemap_urls),
            len(product_sitemaps),
            self.MAX_SITEMAPS,
        )
        for sm in product_sitemaps:
            yield scrapy.Request(sm, callback=self.parse_product_sitemap)

    def parse_product_sitemap(self, response):
        urls = response.xpath(
            "//*[local-name()='url']/*[local-name()='loc']/text()"
        ).getall()
        logger.info("Sitemap %s has %d URLs", response.url, len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        ld_blocks = _LDJSON_RE.findall(response.text)
        product_data = None
        for block in ld_blocks:
            try:
                obj = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            objs = obj if isinstance(obj, list) else [obj]
            for o in objs:
                if isinstance(o, dict) and o.get("@type") == "Product":
                    product_data = o
                    break
            if product_data:
                break

        if not product_data:
            logger.debug("No Product JSON-LD at %s", response.url)
            return

        product_name = product_data.get("name") or ""
        sku = (
            product_data.get("sku")
            or product_data.get("productID")
            or product_data.get("@id")
            or ""
        )
        sku = str(sku).strip()
        if sku and sku in self.scraped_product_ids:
            return
        if sku:
            self.scraped_product_ids.add(sku)

        offers = product_data.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price") if isinstance(offers, dict) else None

        # Category: derive from breadcrumb if present in the page; otherwise
        # try schema.org category, then leave empty.
        category = product_data.get("category") or ""
        if not category:
            crumbs = response.css(
                "nav.breadcrumb a::text, ol.breadcrumb li a::text"
            ).getall()
            if crumbs:
                category = " > ".join(c.strip() for c in crumbs if c.strip())

        if not product_name or price is None:
            return

        scraped_at = response.headers.get(
            "Date",
            datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT").encode(),
        ).decode("utf-8")

        yield {
            "product_id": sku,
            "product_name": product_name,
            "price": str(price),
            "currency": self.currency,
            "category": category,
            "url": response.url,
            "scraped_at": scraped_at,
        }
