import re
import logging
from urllib.parse import urljoin
import scrapy

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"([\d,]+)円")
_BGN_RE = re.compile(r"/lst/bgn(\d+)/")


class HotpepperJpSpider(scrapy.Spider):
    name = "hotpepper_jp"
    allowed_domains = ["www.hotpepper.jp"]
    start_urls = ["https://www.hotpepper.jp/SA11/lst/"]
    currency = "JPY"
    language = "ja"

    SELECTORS = {
        "card": "div.shopDetailTop",
        "restaurant_name": "h3.shopDetailStoreName a::text",
        "dinner_budget": "p.dinnerBudget::text",
        "lunch_budget": "p.lunchBudget::text",
        "shop_url": "h3.shopDetailStoreName a::attr(href)",
        "next_page": "a[href*='/lst/bgn']::attr(href)",
    }

    def parse(self, response):
        cards = response.css(self.SELECTORS["card"])
        logger.info("Found %d restaurant cards on %s", len(cards), response.url)

        for card in cards:
            name = card.css(self.SELECTORS["restaurant_name"]).get()
            if not name:
                continue
            name = name.strip()

            dinner_raw = card.css(self.SELECTORS["dinner_budget"]).get(default="")
            lunch_raw = card.css(self.SELECTORS["lunch_budget"]).get(default="")
            shop_url = card.css(self.SELECTORS["shop_url"]).get()
            if shop_url and not shop_url.startswith("http"):
                shop_url = urljoin(response.url, shop_url)

            if dinner_raw:
                m = _PRICE_RE.search(dinner_raw)
                price = m.group(1).replace(",", "") if m else None
                yield {
                    "product_name": name,
                    "price": price,
                    "price_text": dinner_raw.strip(),
                    "meal_type": "dinner",
                    "currency": self.currency,
                    "url": shop_url or response.url,
                    "language": self.language,
                }

            if lunch_raw:
                m = _PRICE_RE.search(lunch_raw)
                price = m.group(1).replace(",", "") if m else None
                yield {
                    "product_name": name,
                    "price": price,
                    "price_text": lunch_raw.strip(),
                    "meal_type": "lunch",
                    "currency": self.currency,
                    "url": shop_url or response.url,
                    "language": self.language,
                }

        seen = set()
        for href in response.css(self.SELECTORS["next_page"]).getall():
            full = href if href.startswith("http") else urljoin(response.url, href)
            if full not in seen and full != response.url:
                seen.add(full)
                yield scrapy.Request(full, callback=self.parse)
