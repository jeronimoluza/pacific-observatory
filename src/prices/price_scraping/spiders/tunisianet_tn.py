"""
Spider for tunisianet.com.tn — Tunisia electronics retailer (PrestaShop).

Verified live 2026-08-17: needs -k (SSL cert hostname mismatch, standard
for this host) to load. PrestaShop storefront confirmed via
`prestashop = {...}` JS config block and real TND prices on category
listing pages (e.g. `itemprop="price" class="price">1 169,000 DT`, French
number formatting: comma = decimal separator).

robots.txt -> Sitemap: https://www.tunisianet.com.tn/1_index_sitemap.xml
-> https://www.tunisianet.com.tn/1_fr_0_sitemap.xml (single-file sitemap,
CDATA-wrapped <loc>), 10,237 product URLs matching
/<category-slug>/<id>-<slug>.html. Each PDP has a clean
`<h1 itemprop="name">` title and `<span itemprop="price" content="19.9">`
(no schema.org Product JSON-LD on this theme) — walks the sitemap's
product URLs directly, same pattern as btech_eg/priceoye_pk.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://www.tunisianet.com.tn/1_fr_0_sitemap.xml"
_LOC_RE = re.compile(
    r"<!\[CDATA\[(https://www\.tunisianet\.com\.tn/[a-z0-9-]+/\d+-[a-zA-Z0-9-]+\.html)\]\]>"
)
_NAME_RE = re.compile(r'<h1[^>]*itemprop="name"[^>]*>([^<]+)</h1>')
_PRICE_RE = re.compile(r'itemprop="price"\s+content="([\d.]+)"')
_AVAIL_RE = re.compile(r'"availability"\s*:\s*"([^"]+)"')


class TunisianetTnSpider(scrapy.Spider):
    name = "tunisianet_tn"
    allowed_domains = ["tunisianet.com.tn"]
    currency = "TND"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "DOWNLOAD_DELAY": 0.1,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = sorted(set(_LOC_RE.findall(response.text)))
        logger.info("tunisianet_tn: %d product URLs in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        name_m = _NAME_RE.search(response.text)
        price_m = _PRICE_RE.search(response.text)
        if not (name_m and price_m):
            return

        slug_id = response.url.rstrip("/").rsplit("/", 1)[-1].split("-", 1)[0]
        category = response.url.rsplit("/", 2)[-2]

        yield {
            "product_id": slug_id,
            "product_name": name_m.group(1).strip()[:500],
            "category": category,
            "price": price_m.group(1),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
