"""
Spider for 242 Market -- https://242market.com/ (Congo Republic / Congo-
Brazzaville grocery e-commerce, diaspora-facing: "la plateforme qui
rapproche la diaspora congolaise de ses proches").

Confirmed live 2026-09-06. Plain `requests`/curl 200s fine, no anti-bot.
PrestaShop-family PDP markup with clean schema.org microdata:
`itemprop="price" content="0.99"`, `itemprop="priceCurrency"
content="EUR"`, `itemprop="sku"`, breadcrumb `.ProductCategory
itemprop="category"`. `/sitemap.xml` lists all 533 PDP URLs directly
(`/<id>-<slug>.html`), so this spider seeds from the sitemap rather than
crawling category pages.

CURRENCY CAVEAT: prices are denominated in EUR, not XAF (Congo Republic's
currency per countries.yaml). This is a diaspora gifting-service model --
a buyer abroad pays in EUR for groceries delivered to family inside
Congo -- so the EUR price reflects a cross-border remittance-in-kind
service, not necessarily a 1:1 organic local retail price. Emitted as
EUR (the site's own stated currency, per the onboarding convention of
using the site's explicit currency over the country default) with this
caveat recorded in the YAML notes for downstream PPP analysts to weigh.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://242market.com"
_SITEMAP_URL = f"{_BASE}/sitemap.xml"

_LDJSON_RE = re.compile(
    r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S
)


class Market242CgSpider(scrapy.Spider):
    name = "market242_cg"
    allowed_domains = ["242market.com"]
    currency = "EUR"
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
        logger.info("market242_cg: %d PDP urls in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_pdp)

    def parse_pdp(self, response):
        # Microdata was dropped (2026-10); the PDP now carries a JSON-LD
        # ProductGroup whose hasVariant entries each have their own offer.
        for raw in _LDJSON_RE.findall(response.text):
            try:
                node = json.loads(raw)
            except ValueError:
                continue
            if node.get("@type") == "ProductGroup":
                variants = node.get("hasVariant") or []
            elif node.get("@type") == "Product":
                variants = [node]
            else:
                continue
            for variant in variants:
                item = self._variant_item(variant, node, response.url)
                if item:
                    yield item

    def _variant_item(self, variant, group, page_url):
        offer = variant.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        name = (variant.get("name") or "").strip()
        try:
            price = float(offer.get("price"))
        except (TypeError, ValueError):
            return None
        if not name:
            return None
        return {
            "product_id": variant.get("sku") or variant.get("url") or page_url,
            "product_name": name[:500],
            "category": group.get("category"),
            "price": price,
            "currency": offer.get("priceCurrency") or self.currency,
            "available": "InStock" in (offer.get("availability") or ""),
            "url": variant.get("url") or page_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
