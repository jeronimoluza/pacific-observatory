"""
Spider for Pasar Tani (Malaysia) — pasartani.net.

Farmer-direct classifieds marketplace built on DJ-Classifieds (Joomla).
Category listing pages (/browse/<category>-<id>.html) render each advert as
a row with the product name (image alt), the ad URL, an integer MYR price
(span.price_val) and its category — all server-side, so we scrape the
listing rows directly without visiting each advert. Category links are
discovered from /browse.html; location-facet categories (slug ending in
"l.html") are skipped because they only re-list the same adverts.

Note: DJ-Classifieds stores the ad price as an integer in the local
currency; any decimal precision lives only in the free-text description and
is not extracted here.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://pasartani.net"
_BROWSE = _BASE + "/browse.html"
_LOCATION_SLUG = re.compile(r"l\.html$")
_AD_ID = re.compile(r"-(\d+)\.html$")


class PasarTaniSpider(scrapy.Spider):
    name = "pasar_tani"
    allowed_domains = ["pasartani.net"]
    start_urls = [_BROWSE]
    currency = "MYR"
    language = "ms"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def parse(self, response):
        seen = set()
        for href in response.css('a[href*="/browse/"]::attr(href)').getall():
            if "/browse/ad/" in href:
                continue
            if "/browse.html" in href:
                continue
            if _LOCATION_SLUG.search(href):
                continue
            url = urljoin(_BASE, href)
            if url in seen:
                continue
            seen.add(url)
            yield scrapy.Request(url, callback=self.parse_category)

    def parse_category(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in response.css("div.item_row"):
            link = row.css('a[href*="/browse/ad/"]::attr(href)').get()
            if not link:
                continue
            name = row.css('a[href*="/browse/ad/"] img::attr(alt)').get()
            if not name:
                continue
            price = row.css("div.item_col.price span.price_val::text").get()
            if not price:
                continue
            category = row.css("div.item_col.cat_name a::text").get()
            m = _AD_ID.search(link)
            yield {
                "product_id": m.group(1) if m else None,
                "product_name": name.strip(),
                "price": price.strip(),
                "currency": self.currency,
                "category": category.strip() if category else None,
                "url": urljoin(_BASE, link.strip()),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
