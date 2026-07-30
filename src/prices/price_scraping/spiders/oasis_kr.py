"""
Spider for Oasis Market (South Korea) - https://www.oasis.co.kr
Organic/fresh grocer specialty-leaf source. Scoped to categories that fill
thin deep COICOP leaves largely absent from emart_kr/kurly_kr/street11_kr:
  - 01.1.7.4.6 edible seaweed (김/미역/다시마) -- categories 19, 215
  - 01.1.3.2.x / 01.1.3.5.x dried/salted seafood (건어물/멸치/오징어채) -- 18, 244, 1274
  - 01.1.7.5.x tubers (고구마/감자) -- no dedicated nav category, so these
    two use the site's own /product/search endpoint instead.

Both listing and search-result pages are server-rendered (~650KB) with the
same `a.listTit` (name + PDP href) / `span.price_discount b` (price) markup,
60 cards per page at rows=60. No Playwright needed.
"""

import logging

import scrapy

logger = logging.getLogger(__name__)


class OasisKrSpider(scrapy.Spider):
    name = "oasis_kr"
    allowed_domains = ["oasis.co.kr", "www.oasis.co.kr"]
    currency = "KRW"

    # (url, category_label) -- category-nav pages carry a real categoryId;
    # search pages don't, so those use the search keyword as the label.
    START_URLS: list[tuple[str, str]] = [
        (
            "https://www.oasis.co.kr/product/list?categoryId=19&page=1"
            "&sort=priority&direction=desc&rows=60",
            "김│건어물",  # seaweed / dried fish
        ),
        (
            "https://www.oasis.co.kr/product/list?categoryId=215&page=1"
            "&sort=priority&direction=desc&rows=60",
            "수산│건어물",  # seafood / dried goods
        ),
        (
            "https://www.oasis.co.kr/product/list?categoryId=18&page=1"
            "&sort=priority&direction=desc&rows=60",
            "새우│멸치",  # shrimp / anchovy
        ),
        (
            "https://www.oasis.co.kr/product/list?categoryId=244&page=1"
            "&sort=priority&direction=desc&rows=60",
            "오징어│알류",  # squid / roe
        ),
        (
            "https://www.oasis.co.kr/product/list?categoryId=1274&page=1"
            "&sort=priority&direction=desc&rows=60",
            "수산",  # seafood, general
        ),
        (
            "https://www.oasis.co.kr/product/search?keyword=%EA%B3%A0%EA%B5%AC%EB%A7%88",
            "고구마",  # sweet potato
        ),
        (
            "https://www.oasis.co.kr/product/search?keyword=%EA%B0%90%EC%9E%90",
            "감자",  # potato
        ),
        (
            "https://www.oasis.co.kr/product/search?keyword=%ED%86%A0%EB%9E%80",
            "토란",  # taro
        ),
    ]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    async def start(self):
        for url, category in self.START_URLS:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={"category": category},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        cards = response.css("div.wrapInfo")
        yielded = 0
        for card in cards:
            link = card.css("a.listTit")
            href = link.attrib.get("href", "")
            product_id = None
            if "/product/detail/" in href:
                product_id = href.split("/product/detail/")[1].split("?")[0]
            name = " ".join(t.strip() for t in link.css("::text").getall() if t.strip())
            price = (
                card.css("div.info_price span.price_discount b::text").get()
                or card.css("div.info_price span.price_original b::text").get()
            )
            if not product_id or not name or not price:
                continue
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": price.replace(",", ""),
                "currency": self.currency,
                "category": category,
                "url": f"https://www.oasis.co.kr/product/detail/{product_id}",
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1
        logger.info(
            f"oasis_kr: yielded {yielded} cards from {response.url} ({category})"
        )
