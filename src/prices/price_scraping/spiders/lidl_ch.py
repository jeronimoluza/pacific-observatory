"""
Spider for Lidl Schweiz (Switzerland) -- https://www.lidl.ch/.

Unlike the ODS/Vue storefronts used by lidl_gr / lidl_si / lidl_rs, the
Swiss site is Nuxt-rendered and its `/c/<locale>/<slug>/s<id>` category
pages carry no `data-grid-data` blobs (all 500 de-CH category URLs in the
sitemap were scanned on 2026-09-11 and none had one). The PDPs do carry
schema.org JSON-LD, and Lidl publishes a gzipped product sitemap listing
every PDP, so this spider walks that sitemap and parses JSON-LD.

Probed live 2026-09-11:
  https://www.lidl.ch/p/export/CH/de/product_sitemap.xml.gz -> 538 PDP URLs
  https://www.lidl.ch/p/de-CH/acentino-olivenoel-extra-nativ/p10058651
      -> HTTP 200, JSON-LD Product: "Olivenol extra nativ", CHF 9.99
The 538 products span food (pasta, olive oil, crackers, bread), clothing,
homeware, tools and electronics -- i.e. COICOP 01, 03, 05, 09, 12. Items
that are out of stock publish an Offer with a null price and are dropped.

Page family parsed: PDP (JSON-LD). Currency comes from the site's own
`priceCurrency` (CHF), not from countries.yaml.
"""

import gzip
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.lidl.ch"
_SITEMAP = "https://www.lidl.ch/p/export/CH/de/product_sitemap.xml.gz"
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_LD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S
)


class LidlChSpider(scrapy.Spider):
    name = "lidl_ch"
    allowed_domains = ["lidl.ch"]
    currency = "CHF"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        body = response.body
        try:
            text = gzip.decompress(body).decode("utf-8", "replace")
        except (OSError, EOFError):
            text = response.text
        urls = _LOC_RE.findall(text)
        logger.info(f"lidl_ch: product sitemap -> {len(urls)} PDP urls")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for m in _LD_RE.finditer(response.text):
            try:
                payload = json.loads(m.group(1))
            except ValueError:
                continue
            nodes = payload if isinstance(payload, list) else [payload]
            for node in nodes:
                if not isinstance(node, dict) or node.get("@type") != "Product":
                    continue
                offers = node.get("offers")
                if isinstance(offers, dict):
                    offers = [offers]
                if not isinstance(offers, list):
                    continue
                for offer in offers:
                    if not isinstance(offer, dict):
                        continue
                    price = offer.get("price")
                    if not isinstance(price, (int, float)):
                        continue
                    name = (node.get("name") or "").strip()
                    if not name:
                        continue
                    brand = node.get("brand")
                    brand_name = (
                        brand.get("name") if isinstance(brand, dict) else None
                    ) or ""
                    full_name = f"{brand_name} {name}".strip() if brand_name else name
                    yield {
                        "product_id": str(
                            node.get("sku") or node.get("productID") or ""
                        ),
                        "product_name": full_name,
                        "category": node.get("category"),
                        "price": str(price),
                        "currency": offer.get("priceCurrency") or self.currency,
                        "url": response.url,
                        "language": self.language,
                        "scraped_at_utc": scraped_at,
                    }
                    return
