"""J-Mart Liberia -- https://www.jmartliberia.com/

Monrovia general-merchandise retailer ("J-mart") running **Odoo eCommerce**
(server header `Odoo.sh`). Furniture, home appliances, electronics, kitchen
and household goods.

Probed live 2026-09-12 with curl_cffi impersonate=chrome124:
  * /sitemap.xml -> 942 <loc>, of which 697 are /shop/<slug>-<id> product
    pages (the remaining /shop/category/* and static pages are filtered out
    by PRODUCT_URL_RE). Sitemap enumeration, so no gallery pagination needed.
  * PDPs are fully server-rendered Odoo microdata -- NOT schema.org JSON-LD.
    The repo's rows_from_jsonld / row_from_meta helpers both return 0 rows on
    this tenant (measured), which is why this spider parses the microdata
    itself rather than subclassing _jsonld_sitemap_base:
        <span itemprop="price" ...>1,699.00</span>
        <span itemprop="priceCurrency">US</span>
        <h1>Sofa Set 3+2+1 | Fabric | Valencia 050</h1>

CURRENCY: the tenant's own `itemprop="priceCurrency"` says **"US"**, which is
not a valid ISO 4217 code -- an Odoo currency-symbol misconfiguration. The
rendered price is prefixed "$" and Liberia's formal retail segment is
dollarized, so the currency is forced to USD here rather than trusting the
page. Flagged, not silently assumed.

Page family parsed: PDP.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_ID_RE = re.compile(r"-(\d+)$")


class JmartliberiaSpider(scrapy.Spider):
    name = "jmartliberia"
    allowed_domains = ["jmartliberia.com", "www.jmartliberia.com"]
    currency = "USD"
    language = "en"

    SITEMAP_URL = "https://www.jmartliberia.com/sitemap.xml"
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
