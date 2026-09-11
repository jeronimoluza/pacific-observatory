"""Beares Botswana — Magento 2 furniture/appliance/electronics chain.

Shared Magento tenant across co.za/co.ls/co.bw/co.na/co.sz (confirmed via
robots.txt sitemap entries listing all five TLDs and via the store's own
/media/sitemap.xml, which is misconfigured to serve co.za urls even when
fetched from the .co.bw host -- do NOT use that sitemap for enumeration).
Each TLD is a distinct Magento store_id/currency: store_id=2 on .co.bw emits
currency_code=BWP in product:price:currency meta, itemprop=priceCurrency,
klevu_baseCurrencyCode, and the productCurrent JS blob -- all confirmed from
the .co.bw page payload itself, not assumed from the TLD.

No open GraphQL/REST catalog endpoint found (unlike mm_mega_market /
sm_markets_savemore in platform_fingerprints.md); category grid pages are
server-rendered HTML with price already inlined
(`[data-price-amount]` inside each `li.product-item`), so this is a plain
Tier 1A scrapy_html CrawlSpider over the "shop-by-product" category tree,
never visiting individual PDPs.

Enumerability verified live: /shop-by-product/appliances page1 (no ?p) vs
page1?p=2 return DISJOINT id sets ({1664,1696,1697,1698,1721,1734,1740} vs
{1545}).

Page family: listing only (category grid), never PDP.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

CATEGORIES = [
    "appliances",
    "audio-visual",
    "bed-sets",
    "bedding",
    "computers",
    "cookware",
    "furniture",
    "home-decor",
]
MAX_PAGES = 15


class BearesBwSpider(scrapy.Spider):
    name = "beares_bw"
    allowed_domains = ["beares.co.bw"]
    currency = "BWP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for cat in CATEGORIES:
            yield scrapy.Request(
                f"https://www.beares.co.bw/shop-by-product/{cat}",
                callback=self.parse_listing,
                meta={"cat": cat, "page": 1},
            )

    def parse_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select("li.product-item")
        cat = response.meta["cat"]
        page = response.meta["page"]
        count = 0
        for item in items:
            link = item.select_one(".product-item-name a") or item.select_one(
                "a.product-item-link"
            )
            price_el = item.select_one("[data-price-amount]")
            if not link or not price_el:
                continue
            url = link.get("href")
            m = re.search(r"/id/(\d+)/", url or "")
            product_id = m.group(1) if m else None
            price = price_el.get("data-price-amount")
            name = link.get_text(strip=True)
            if not name or not price:
                continue
            try:
                if float(price) == 0:
                    continue
            except (TypeError, ValueError):
                continue
            count += 1
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": cat,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if count > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"https://www.beares.co.bw/shop-by-product/{cat}?p={nxt}",
                callback=self.parse_listing,
                meta={"cat": cat, "page": nxt},
            )
