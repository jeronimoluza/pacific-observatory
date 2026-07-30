"""
Spider for scraping Amica Shop (Japan) - https://www.amicashop.com/

Amica ("業務用食品スーパーアミカ") is a food-service/wholesale grocery
distributor with a plain server-rendered HTML catalogue (no login/area
gate, unlike AEON Netsuper / Rakuten Mart which require a delivery
postal code before showing products or SPA-hydrate their listings).

Strategy:
1. Targeted keyword search instead of a full-catalog crawl, so we only
   pull the deep COICOP leaves this source was onboarded for:
   - Edible seaweed (01.1.7.4.6): kombu, wakame, nori, hijiki, kaisou
   - Dried/salted/smoked fish (01.1.3.2.x / 01.1.3.5.x): shirasu,
     katsuobushi, niboshi, kezuribushi, himono
   - Tubers (01.1.7.5.x): satsumaimo, satoimo, yamaimo
   Each keyword hits /products/list?name=<kw>&disp_number=96 (96 is the
   site's max page size). Note: the site's `page=`/`pageno=` params did
   NOT change results in manual probing (server ignores them on plain
   GET, likely AJAX-only pagination) so keywords with >96 hits (e.g.
   kombu, 143 results) are capped at the first 96.
2. Each listing page is plain HTML with direct /products/detail/{id}
   links - no hydration needed.
3. Product pages expose name (h1.item_name) and price
   (.item_price .price_str) directly in the server-rendered HTML.
"""

import logging
import re
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_SEARCH_KEYWORDS = [
    # Edible seaweed & aquatic plants - 01.1.7.4.6
    "昆布",
    "わかめ",
    "海苔",
    "ひじき",
    "海藻",
    # Dried/salted/smoked fish & seafood - 01.1.3.2.x / 01.1.3.5.x
    "しらす",
    "鰹節",
    "煮干し",
    "削り節",
    "干物",
    # Tubers - 01.1.7.5.x
    "さつまいも",
    "里芋",
    "山芋",
]

_LISTING_URL = "https://www.amicashop.com/products/list?name={keyword}&disp_number=96"


class AmicashopJpSpider(scrapy.Spider):
    """
    Spider for Amica Shop (Japan).
    Runs one search per deep-leaf keyword and follows every product link
    on the results page.
    """

    name = "amicashop_jp"
    allowed_domains = ["www.amicashop.com"]
    currency = "JPY"

    def start_requests(self):
        for keyword in _SEARCH_KEYWORDS:
            url = _LISTING_URL.format(keyword=quote(keyword))
            yield scrapy.Request(
                url, callback=self.parse_listing, meta={"category": keyword}
            )

    def parse_listing(self, response):
        category = response.meta.get("category")
        seen = set()
        # Anonymous sessions on this site start 401-ing product-detail views
        # after ~50-60 consecutive views (observed empirically: clean 200s
        # for the first ~54 requests, then near-100% 401 for the rest of the
        # run). Since a full run's product budget is spent well before all
        # 13 keyword listings are exhausted, prioritize by in-listing index
        # (0, 1, 2, ...) rather than listing order: Scrapy's scheduler is a
        # priority queue, so every keyword's position-0 product is dequeued
        # before any keyword's position-1 product, giving round-robin
        # coverage across seaweed / dried-fish / tuber keywords instead of
        # exhausting the session budget on whichever keyword was queued
        # first.
        idx = 0
        for href in response.css("a::attr(href)").getall():
            if "/products/detail/" not in href:
                continue
            if href in seen:
                continue
            seen.add(href)
            yield response.follow(
                href,
                callback=self.parse_product,
                meta={"category": category},
                priority=-idx,
            )
            idx += 1

    def parse_product(self, response):
        product_name = response.css("h1.item_name::text").get()
        if product_name:
            product_name = product_name.strip()

        price_int = response.css(".item_price .price_str::text").get()
        price = None
        if price_int:
            cleaned = re.sub(r"[^\d.]", "", price_int)
            if cleaned:
                price = float(cleaned)

        product_id = None
        match = re.search(r"/products/detail/(\d+)", response.url)
        if match:
            product_id = match.group(1)

        category = response.meta.get("category")

        if product_name and price:
            yield {
                "product_name": product_name,
                "category": category,
                "price": price,
                "product_id": product_id,
                "currency": self.currency,
                "url": response.url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name} (category: {category})")
        else:
            logger.warning(f"Could not extract product data from {response.url}")
