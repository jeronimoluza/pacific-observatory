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

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://242market.com"
_SITEMAP_URL = f"{_BASE}/sitemap.xml"

_PRICE_RE = re.compile(r'class="Price-value"\s+itemprop="price"\s+content="([\d.]+)"')
_CURRENCY_RE = re.compile(r'itemprop="priceCurrency"\s+content="([A-Z]{3})"')
_SKU_RE = re.compile(r'itemprop="sku">([^<]*)</span>')
_CATEGORY_RE = re.compile(r'itemprop="category">([^<]*)</a>')
_TITLE_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)


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
        html = response.text
        price_m = _PRICE_RE.search(html)
        if not price_m:
            return
        title_m = _TITLE_RE.search(html)
        if not title_m:
            return
        name = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        if not name:
            return

        currency_m = _CURRENCY_RE.search(html)
        sku_m = _SKU_RE.search(html)
        category_m = _CATEGORY_RE.search(html)

        yield {
            "product_id": sku_m.group(1).strip() if sku_m else response.url,
            "product_name": name[:500],
            "category": category_m.group(1).strip() if category_m else None,
            "price": float(price_m.group(1)),
            "currency": currency_m.group(1) if currency_m else self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
