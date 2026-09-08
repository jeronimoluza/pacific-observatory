"""
Spider for EcoFamily (Hungary) -- https://ecofamily.hu/.

Nationwide food + drogerie delivery on the UNAS webshop platform (Hungarian
SaaS e-commerce, unrelated to Shopify/WooCommerce). robots.txt points at a
gzipped sitemap index -> a single gzipped urlset
(sitemap-ecofamily_hu-1.xml.gz, ~17.8k urls: 950 category pages under
`/c/`, 14,055 product-detail pages under `/p/<slug>`) -- confirmed live
2026-09-06, so this walks the PDP list directly rather than the
AJAX-driven category listing (`?action=cat_art_list&ajax=1`, also open,
but the sitemap is simpler and gives full catalog coverage without
per-category pagination).

Each PDP carries a `schema.org/Product` JSON-LD block (`name`,
`offers.price`, `offers.priceCurrency`) and a `BreadcrumbList` block whose
last item is the leaf category. Sample verified live: "Bref Deluxe
Delicate Magnolia WC frissito 3 x 50 g", HUF 1590, breadcrumb ... ->
Haztartas > Tisztitoszerek > WC tisztito, fertotlenito > WC illatosito.
"""

import gzip
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://ecofamily.hu/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_PDP_STRIDE = 3  # sample every Nth PDP from the sitemap (~4.7k of ~14k)


class EcofamilyHuSpider(scrapy.Spider):
    name = "ecofamily_hu"
    allowed_domains = ["ecofamily.hu"]
    currency = "HUF"
    language = "hu"

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

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        shards = _LOC_RE.findall(response.text)
        logger.info("ecofamily_hu: %d sitemap shards", len(shards))
        for shard in shards:
            yield scrapy.Request(shard, callback=self.parse_sitemap_shard)

    def parse_sitemap_shard(self, response):
        # Server sends content-type: application/x-gzip with NO
        # Content-Encoding header, so Scrapy does not auto-decompress --
        # response.body is the raw gzip bytes (confirmed live 2026-09-06).
        try:
            xml_text = gzip.decompress(response.body).decode("utf-8")
        except OSError:
            logger.warning("ecofamily_hu: could not gunzip %s", response.url)
            return
        locs = _LOC_RE.findall(xml_text)
        product_urls = [loc for loc in locs if "/p/" in loc]
        sampled = product_urls[::_PDP_STRIDE]
        logger.info(
            "ecofamily_hu: sampled %d/%d product urls", len(sampled), len(product_urls)
        )
        for url in sampled:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        category = None
        for block in _LD_JSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (ValueError, TypeError):
                continue
            if data.get("@type") == "Product":
                product = data
            elif data.get("@type") == "BreadcrumbList":
                items = data.get("itemListElement", [])
                if items:
                    category = items[-1].get("name")

        if not product:
            logger.warning("ecofamily_hu: no Product JSON-LD on %s", response.url)
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0):
            return

        yield {
            "product_id": product.get("sku") or product.get("gtin13") or response.url,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in (offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
