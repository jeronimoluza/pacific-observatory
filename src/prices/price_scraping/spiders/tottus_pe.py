"""
Spider for Tottus Peru -- https://www.tottus.com.pe/tottus-pe.

Falabella-Group supermarket banner, same Next.js "Catalyst" shell family as
sodimac_pe.py / homecenter_co.py (shared businessUnit=falabella,
catalystBaseUrl/atgBaseUrl fields in __NEXT_DATA__), but a DIFFERENT
gotcha: every `/tottus-pe/lista/<catId>/<slug>` category-listing URL 302s
back to the homepage regardless of cookies (confirmed live 2026-09-06 --
even a fresh cookie-less request redirects; `vary: Cookie, X-Zone-Id`
gates listing content on a delivery-zone selection this spider never
performs). Category-listing enumeration is therefore not viable here.

PDP pages are NOT zone-gated and return 200 directly. robots.txt exposes
a clean PDP sitemap
(static/site/sitemaps/pdp/pdp_pe_TO_COM-index.xml -> two shards,
~31.8k product URLs total, confirmed live). Each PDP embeds
__NEXT_DATA__.props.pageProps.productData with a `variants[]` array
carrying `prices[]` ({type, crossed, price}) -- the entry with
crossed=false is the actually-charged price, same convention as
sodimac_pe. Category comes from `breadCrumb[-1].label`.

Verified live 2026-09-06: PDP 146700547 "Chompa Cuello Redondo Hombre
Redwood" -> internetPrice S/ 16.90 (crossed=false) vs normalPrice S/ 39.90
crossed=true. This walks the PDP sitemap directly (the "numeric-id-walk"
pattern applied to a slug-based PDP sitemap instead of live URL
enumeration) rather than category listings.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = (
    "https://www.tottus.com.pe/static/site/sitemaps/pdp/pdp_pe_TO_COM-index.xml"
)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_PDP_STRIDE = 15  # sample every Nth PDP from the sitemap (~2100 of ~31.8k)


def _effective_price(prices: list) -> str | None:
    for p in prices:
        if p.get("crossed") is False and p.get("price"):
            return p["price"][0]
    for p in prices:
        if p.get("price"):
            return p["price"][0]
    return None


class TottusPeSpider(scrapy.Spider):
    name = "tottus_pe"
    allowed_domains = ["tottus.com.pe"]
    currency = "PEN"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
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
        logger.info("tottus_pe: %d PDP sitemap shards", len(shards))
        for shard in shards:
            yield scrapy.Request(shard, callback=self.parse_sitemap_shard)

    def parse_sitemap_shard(self, response):
        urls = _LOC_RE.findall(response.text)
        sampled = urls[::_PDP_STRIDE]
        logger.info(
            "tottus_pe: sampled %d/%d PDP urls from %s",
            len(sampled),
            len(urls),
            response.url,
        )
        for url in sampled:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("tottus_pe: no __NEXT_DATA__ at %s", response.url)
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning("tottus_pe: bad __NEXT_DATA__ JSON at %s", response.url)
            return
        product = data.get("props", {}).get("pageProps", {}).get("productData")
        if not product:
            logger.warning("tottus_pe: no productData at %s", response.url)
            return

        name = (product.get("name") or "").strip()
        product_id = str(product.get("id") or "")
        breadcrumb = product.get("breadCrumb") or []
        category = breadcrumb[-1].get("label") if breadcrumb else None

        variants = product.get("variants") or []
        price = None
        for variant in variants:
            price = _effective_price(variant.get("prices") or [])
            if price is not None:
                break

        if not name or not product_id or price is None:
            return

        yield {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": bool(product.get("isPublished", True)),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
