"""Modelsville Group -- https://modelsvillegroup.com/

Monrovia general-merchandise / appliance retailer running **Odoo eCommerce**
(same platform as jmartliberia in this directory). Its own PDPs state
"Available in Liberia Only". Catalog: air conditioners, kitchen and household
appliances, electronics, solar products, bottled water/beverages.

Probed live 2026-09-12 with curl_cffi impersonate=chrome124:
  * /sitemap.xml -> 418 <loc>, of which 266 are /shop/<slug>-<id> product
    pages (the rest are /shop/category/*, /jobs/* and static pages, filtered
    by PRODUCT_URL_RE). Sitemap enumeration, no gallery pagination.
  * PDPs are server-rendered Odoo microdata, NOT schema.org JSON-LD -- the
    repo's rows_from_jsonld / row_from_meta helpers return 0 rows here
    (measured), so this spider reads the microdata directly:
        <span itemprop="price" ...>150.0</span>
        <span itemprop="priceCurrency">USD</span>
        <h1>Serenelife Slacht108 Portable Room Air Conditioner and Heater</h1>

CURRENCY: USD, and unlike the sibling jmartliberia tenant this one emits a
valid ISO 4217 `priceCurrency` ("USD") of its own. Still pinned at the class
level rather than read per page, because Liberia is a dual-currency USD/LRD
economy and a silent per-page flip would be invisible downstream.

Page family parsed: PDP.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_ID_RE = re.compile(r"-(\d+)$")


class ModelsvilleMarketplaceSpider(scrapy.Spider):
    name = "modelsville_marketplace"
    allowed_domains = ["modelsvillegroup.com", "www.modelsvillegroup.com"]
    currency = "USD"
    language = "en"

    SITEMAP_URL = "https://modelsvillegroup.com/sitemap.xml"
    PRODUCT_URL_RE = r"/shop/(?!category/)"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(self.SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text)
                if re.search(self.PRODUCT_URL_RE, u)]
        self.logger.info(f"{self.name}: {len(urls)} product urls in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        price = response.css('span[itemprop="price"]::text').get()
        name = response.css("h1::text").get()
        if not name:
            name = response.css('meta[property="og:title"]::attr(content)').get()
        if not price or not name:
            return
        price = price.strip().replace(",", "")
        try:
            if float(price) <= 0:
                return
        except ValueError:
            return
        m = _ID_RE.search(response.url)
        yield {
            "product_id": m.group(1) if m else None,
            "product_name": name.strip()[:500],
            "price": price,
            "currency": self.currency,
            "category": None,
            "url": response.url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
