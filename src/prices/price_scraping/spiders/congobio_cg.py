"""
Spider for CongoBio -- https://www.congobio.net/ (Congo Republic /
Congo-Brazzaville organic-produce and farm-direct e-commerce:
"Produits bio en ligne -- Congo Brazzaville").

Confirmed live 2026-09-11 with curl_cffi impersonate="chrome124" (site
is Cloudflare-fronted, 200 on homepage and PDPs, no challenge observed).
Next.js/Turbopack frontend -- no public JSON API discovered
(/api/products, /api/produits both 404). `/sitemap.xml` lists all PDP
URLs directly (`/produit/<uuid>`), so this spider seeds from the
sitemap. Each PDP embeds a clean schema.org Product JSON-LD block with
offers.priceCurrency / offers.price -- used instead of microdata.

CURRENCY: prices are in XAF, Congo Republic's own currency per
countries.yaml (confirmed from the JSON-LD payload itself, not
inferred) -- no diaspora/remittance markup caveat needed here, unlike
market242_cg (EUR) and mbote_cg is also native XAF.

Catalog is small (40 product URLs in sitemap as of 2026-09-11) -- a
farm-direct site selling live poultry, farm produce and livestock
(COICOP 01.1), not a supermarket. Small but real and enumerable.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.congobio.net"
_SITEMAP_URL = f"{_BASE}/sitemap.xml"

_JSONLD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)


class CongobioCgSpider(scrapy.Spider):
    name = "congobio_cg"
    allowed_domains = ["congobio.net"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        urls = [u for u in urls if "/produit/" in u]
        logger.info("congobio_cg: %d PDP urls in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_pdp)

    def parse_pdp(self, response):
        for block in _JSONLD_RE.findall(response.text):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if data.get("@type") != "Product":
                continue

            offers = data.get("offers") or {}
            price = offers.get("price")
            if price is None:
                continue
            name = (data.get("name") or "").strip()
            if not name:
                continue

            yield {
                "product_id": response.url.rsplit("/", 1)[-1],
                "product_name": name[:500],
                "category": data.get("category"),
                "price": float(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": True,
                "url": response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            return
