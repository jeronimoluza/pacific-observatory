"""
Spider for Domod (Bosnia and Herzegovina) - domod.ba, electronics/appliances
retailer.

Server-rendered category listing pages at /shop/<department>?page=N. Each
product card is `div.item article.list-product`: `a[href^=".../shop/proizvod/"]`
for the URL, `h2` for the name, `span[data-price]` for the price (KM,
verified "429,00 <mark>KM</mark>" / data-price="429.00"), and the trailing
URL path segment (also mirrored as `data-product-id` on the add-to-basket
link) for a stable SKU id. Pagination is plain `?page=N`, ~12 products/page;
the page past the last one renders zero `list-product` cards (verified on
bijela-tehnika: 42 real pages, page 43 empty), so the spider stops there.
13 top-level department slugs (from the /shop nav) are walked directly -
each already lists its whole department across all pages, no subcategory
drill-down needed.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://domod.ba"

_DEPARTMENTS = [
    "alati-i-masine",
    "bijela-tehnika",
    "dekoracija-i-aksesoari",
    "elektro-i-vodo-materijal",
    "foto-oprema-i-kamere",
    "it-oprema",
    "kuhinjska-oprema-i-posude",
    "mali-kucanski-aparati",
    "sport-i-rekreacija",
    "telefonija",
    "televizori-av-oprema",
    "ugradbena-tehnika",
]

_MAX_PAGES = 80


class DomodBaSpider(scrapy.Spider):
    name = "domod_ba"
    allowed_domains = ["domod.ba"]
    currency = "BAM"
    language = "bs"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug in _DEPARTMENTS:
            yield scrapy.Request(
                f"{_BASE}/shop/{slug}?page=1",
                callback=self.parse_list,
                cb_kwargs={"slug": slug, "page": 1},
            )

    def parse_list(self, response, slug, page):
        cards = response.css("article.list-product")
        if not cards:
            logger.info("domod_ba: %s page %d empty, stopping", slug, page)
            return

        for card in cards:
            href = card.css("a::attr(href)").get()
            name = card.css("h2::text").get()
            price = card.css("span[data-price]::attr(data-price)").get()
            if not (href and name and price):
                continue
            product_id = href.rstrip("/").rsplit("/", 1)[-1]
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if page >= _MAX_PAGES:
            logger.warning("domod_ba: %s hit page cap %d", slug, _MAX_PAGES)
            return

        next_page = page + 1
        yield scrapy.Request(
            f"{_BASE}/shop/{slug}?page={next_page}",
            callback=self.parse_list,
            cb_kwargs={"slug": slug, "page": next_page},
        )
