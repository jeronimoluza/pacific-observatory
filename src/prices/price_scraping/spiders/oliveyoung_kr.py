"""
Olive Young Korea best-seller spider.

The best-list page is server-rendered enough for Scrapy: each product card
contains goodsNo, brand/name, category metadata, and current/original KRW
prices. Use curl_cffi Chrome impersonation because the storefront is picky
about plain bot fingerprints.
"""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import scrapy


BEST_URL = "https://www.oliveyoung.co.kr/store/main/getBestList.do"


class OliveYoungKrSpider(scrapy.Spider):
    name = "oliveyoung_kr"
    allowed_domains = ["oliveyoung.co.kr", "www.oliveyoung.co.kr"]
    currency = "KRW"
    language = "ko"

    IMPERSONATE_PROFILE = "chrome"
    CHROME_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "COOKIES_ENABLED": False,
        "USER_AGENT": CHROME_UA,
        "RETRY_TIMES": 3,
        "ROBOTSTXT_OBEY": False,
    }

    async def start(self):
        yield scrapy.Request(
            BEST_URL,
            callback=self.parse_best,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
            headers={"User-Agent": self.CHROME_UA},
        )

    def parse_best(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("div.prd_info"):
            product_link = card.css("div.prd_name a::attr(href)").get() or card.css(
                "a.prd_thumb::attr(href)"
            ).get()
            brand = card.css("span.tx_brand::text").get(default="").strip()
            name = card.css("p.tx_name::text").get(default="").strip()
            price = (
                card.css("p.prd_price span.tx_cur span.tx_num::text").get()
                or card.css("p.prd_price span.tx_org span.tx_num::text").get()
            )
            if not (name and price):
                continue

            goods_no = card.css("[data-ref-goodsno]::attr(data-ref-goodsno)").get()
            category = card.css("[data-ref-goodscategory]::attr(data-ref-goodscategory)").get()
            if not goods_no and product_link:
                goods_no = (
                    parse_qs(urlparse(product_link).query).get("goodsNo") or [None]
                )[0]

            product_name = f"{brand} {name}".strip()
            yield {
                "product_id": goods_no or product_link,
                "product_name": product_name[:500],
                "category": category,
                "price": price.replace(",", "").strip(),
                "currency": self.currency,
                "url": response.urljoin(product_link) if product_link else BEST_URL,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

