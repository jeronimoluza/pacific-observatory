"""
Spider for Emart / SSG.com (South Korea) - https://emart.ssg.com/
Listing-card extraction over plain HTTP. The category pages are server-rendered
(~1MB): when the Akamai edge check passes, the raw HTML already carries every
`li.cunit_t232` card with product id, name, and price as data-attributes, so no
Playwright render and no PDP visit is needed. Akamai bot-scores probabilistically
(~1-in-3 to 1-in-2 requests 403), so 403 is retried — each retry is a fresh roll.
"""

import logging

import scrapy

logger = logging.getLogger(__name__)


class EmartKrSpider(scrapy.Spider):
    name = "emart_kr"
    allowed_domains = ["emart.ssg.com", "ssg.com"]
    currency = "KRW"

    # Top-level Emart categories spanning food + non-food (COICOP 01, 05, 09, 12).
    # Each renders ~60 cards on first load.
    START_URLS = [
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000095244",  # 신선식품 fresh
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000213046",  # 건강식품 health
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000228036",  # 친환경/유기농 organic
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000217707",  # 밀키트 meal kits
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000213997",  # 제지/위생/건강 hygiene
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000214658",  # 헤어/바디/뷰티 personal care
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000214420",  # 청소/생활용품 household
        "https://www.ssg.com/disp/category.ssg?dispCtgId=6000214128",  # 주방용품 kitchenware
    ]

    custom_settings = {
        # ssg.com passes chrome124 fingerprints where the global chrome120 fails.
        "IMPERSONATE_BROWSERS": ["chrome124"],
        # Akamai bot-scores probabilistically; retry the 403s until a request rolls
        # through. Each RetryMiddleware attempt re-issues a fresh curl_cffi request.
        "RETRY_HTTP_CODES": [403, 500, 502, 503, 504, 408, 429],
        "RETRY_TIMES": 12,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    async def start(self):
        for url in self.START_URLS:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={"impersonate": "chrome124"},
            )

    def parse_listing(self, response):
        cards = response.css("li.cunit_t232")
        yielded = 0
        for card in cards:
            unit = card.css("[data-react-unit-id]")
            product_id = unit.attrib.get("data-react-unit-id")
            unit_price = unit.attrib.get("data-react-unit-price")
            name = (card.css("div.ssgitem_tit_name::text").get() or "").strip()
            # Promo/rental cards have data-react-unit-price="0" and a monthly
            # price string that starts with "월". Filter those out.
            if not product_id or not name or not unit_price or unit_price == "0":
                continue
            url = (
                f"https://emart.ssg.com/item/itemView.ssg?itemId={product_id}"
                "&siteNo=6001&salestrNo=6005"
            )
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": unit_price,
                "currency": self.currency,
                "category": None,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1
        logger.info(f"emart_kr: yielded {yielded} cards from {response.url}")
