"""
Spider for Satu.kz (https://satu.kz/) -- Kazakhstan's largest general/B2B
marketplace ("Satu -- крупнейшая торговая площадка Казахстана").

Server-rendered HTML with stable `data-qaid` attributes (no WAF, verified
live 2026-09-06 with curl_cffi impersonate=chrome124). Each product tile is
a `[data-qaid="qa_product_tile"]` element carrying a `data-product-id`
attribute, a `[data-qaid="product_link"]` anchor (name text + PDP href),
and a `[data-qaid="product_price"]` element whose `data-qaprice` attribute
is the clean numeric price in KZT (no thousands separators to strip).

Top-level nav links (Odezhda, Bytovaya-tehnika, Mebel, ...) are category
*hub* pages with zero product tiles -- they only link further down to leaf
categories. Rather than crawl the full hub->leaf tree this pass, four
confirmed leaf categories with live product tiles are hard-coded:
Noutbuki (laptops), Smartfony (phones), Holodilniki (fridges), Velosipedy
(bicycles) -- covering electronics/appliances/sport (COICOP 05/09).

Pagination is a `;<n>` URL-path suffix (`https://satu.kz/Noutbuki;2`), not
a query param -- confirmed present in the page's own `next_page` link.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORIES = ["Noutbuki", "Smartfony", "Holodilniki", "Velosipedy"]
_MAX_PAGES = 10


class SatuKzSpider(scrapy.Spider):
    name = "satu_kz"
    allowed_domains = ["satu.kz"]
    currency = "KZT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"https://satu.kz/{slug}",
                callback=self.parse,
                meta={"impersonate": "chrome124", "slug": slug, "page": 1},
            )

    def parse(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        tiles = response.css('[data-qaid="qa_product_tile"]')
        fresh = 0
        for tile in tiles:
            item = self._item(tile, slug, response)
            if item:
                fresh += 1
                yield item
        logger.info(f"satu_kz: {slug} page={page} yielded {fresh} of {len(tiles)} tiles")

        if fresh and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"https://satu.kz/{slug};{nxt}",
                callback=self.parse,
                meta={"impersonate": "chrome124", "slug": slug, "page": nxt},
            )

    def _item(self, tile, slug, response):
        product_id = tile.attrib.get("data-product-id")
        name = tile.css('[data-qaid="product_link"] ::text').get()
        href = tile.css('[data-qaid="product_link"]::attr(href)').get()
        price_el = tile.css('[data-qaid="product_price"]')
        price_raw = price_el.attrib.get("data-qaprice") if price_el else None
        if not (product_id and name and href and price_raw):
            return None
        try:
            price = float(price_raw)
        except ValueError:
            return None
        if price <= 0:
            return None
        return {
            "product_id": product_id,
            "product_name": name.strip(),
            "category": slug,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": response.urljoin(href),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
