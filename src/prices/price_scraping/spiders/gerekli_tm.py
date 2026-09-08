"""
Spider for Gerekli (Turkmenistan) — https://gerekli.tm/.

"Gerekli — крупнейший маркетплейс в Туркменистане". A CS-Cart Multi-Vendor
backend (Android package `com.simtech.multivendor.mk`) behind a Next.js App
Router front end. Turkmenistan is one of the most closed internet markets in
the world, so this is a rare live, un-walled domestic catalogue: no WAF, no
challenge, `robots.txt` is `Allow: /`, and `curl_cffi impersonate=chrome124`
returns 200 on every path tried.

Enumeration comes from the sitemap: https://gerekli.tm/sitemap.xml is a
single 12.5 MB urlset holding 26,594 <loc>s, of which 13,290 are Russian
product permalinks under /ru/products/<slug> (the other half are the Turkmen
/tk/ mirrors of the same products; only /ru/ is crawled, so each product is
visited once). Category listing pages hydrate client-side and were NOT used.

Each PDP server-renders a schema.org Product `<script type="application/
ld+json">` carrying name, sku, category and offers.price/priceCurrency in
MAJOR units (TMT), alongside a BreadcrumbList. This avoids the minor-unit
trap in the page's React payload, where the same product is carried as
`fields.price` in TMT*100 (vase: JSON-LD 559 TMT vs fields.price 55900).
Extraction therefore goes through the shared `rows_from_jsonld` helper.

Measured 2026-09-05 on 20 randomly-sampled product URLs: 19/20 yielded a
priced Product node (the miss was an out-of-stock air conditioner whose
Product node is dropped server-side). Sample rows: 'Кофемашина Ardesto
YCM-E1500' 1975 TMT; 'Шампунь Emeron Hijab Anti Dandruff 170 мл' 21 TMT;
'Развивашки Котик' 10 TMT. Catalogue skews to appliances/home/perfume but
carries a real division-01 tail (кофе в зернах, горячий шоколад, сиропы).

Product names are Russian even though the official language is Turkmen —
`language: ru` is deliberate.

Parses: PDPs only (the sitemap is the listing).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from ..archived import rows_from_jsonld

logger = logging.getLogger(__name__)

_SITEMAP = "https://gerekli.tm/sitemap.xml"
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_PRODUCT_RE = re.compile(r"^https://gerekli\.tm/ru/products/[^/]+$")


class GerekliTmSpider(scrapy.Spider):
    name = "gerekli_tm"
    allowed_domains = ["gerekli.tm"]
    currency = "TMT"
    language = "ru"

    custom_settings = {
        # The origin is unwalled and returned 200 on 110/110 requests in the
        # probe run, so this is tuned for throughput: at the conservative
        # 4-concurrent/0.5s setting the first test ran at ~55 items/min,
        # which would put a full 13,290-product crawl near 4h.
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.25,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        # The sitemap alone is 12.5 MB; keep Scrapy from warning on it.
        "DOWNLOAD_WARNSIZE": 0,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if _PRODUCT_RE.match(u)]
        logger.info("gerekli_tm: %d product URLs in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        rows = rows_from_jsonld(response.text, response.url)
        if not rows:
            logger.debug("gerekli_tm: no Product JSON-LD at %s", response.url)
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in rows:
            row.setdefault("currency", self.currency)
            row.setdefault("product_id", response.url.rstrip("/").rsplit("/", 1)[-1])
            row["language"] = self.language
            row["scraped_at_utc"] = scraped_at
            yield row
