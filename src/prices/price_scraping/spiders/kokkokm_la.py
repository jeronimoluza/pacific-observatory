"""Spider for Kokkok Mart (Lao PDR) - https://kokkokm.com/."""

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import scrapy

logger = logging.getLogger(__name__)


class KokkokmLaSpider(scrapy.Spider):
    name = "kokkokm_la"
    allowed_domains = ["kokkokm.com", "www.kokkokm.com"]
    currency = "LAK"
    language = "multilingual"

    start_urls = ["https://kokkokm.com/ko_KR/shop"]
    max_shop_page = 50

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "CLOSESPIDER_ITEMCOUNT": 800,
        "COOKIES_ENABLED": False,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("form.oe_product_cart"):
            item = self._parse_card(response, card, scraped_at)
            if item:
                yield item

        for href in response.css('ul.pagination a.page-link::attr(href)').getall():
            if self._shop_page_number(href) <= self.max_shop_page:
                yield response.follow(href, callback=self.parse)

        for href in response.css("[data-link-href]::attr(data-link-href)").getall():
            if "/shop/category/" not in href:
                continue
            path = urlparse(href).path
            yield response.follow(f"/ko_KR{path}", callback=self.parse)

    def _parse_card(self, response, card, scraped_at: str):
        href = card.css('a[itemprop="url"]::attr(href)').get()
        name = card.css('a[itemprop="name"]::attr(content)').get() or card.css(
            'a[itemprop="name"]::text'
        ).get()
        price = card.css('span[itemprop="price"]::text').get()
        currency = card.css('span[itemprop="priceCurrency"]::text').get()
        product_id = card.css('input[name="product_id"]::attr(value)').get()

        if not href or not name or price is None:
            return None

        name = " ".join(name.split())
        try:
            value = float(str(price).replace(",", ""))
        except ValueError:
            return None
        if value <= 0 or self._is_placeholder(name):
            return None

        parsed = urlparse(response.urljoin(href))
        clean_url = urlunparse(parsed._replace(query="", fragment=""))
        url_id = parsed.path.rstrip("/").rsplit("-", 1)[-1]
        product_id = url_id if url_id.isdigit() else product_id
        category = self._category_from_url(response.url)

        return {
            "product_id": str(product_id),
            "product_name": name,
            "price": str(int(value)) if value.is_integer() else str(value),
            "currency": self._normalize_currency(currency),
            "category": category,
            "url": clean_url,
            "language": self.language,
            "store": "Kokkok Mart",
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _normalize_currency(currency: str | None) -> str:
        if currency and currency.strip().upper() in {"LAK", "KIP", "LAKIP"}:
            return "LAK"
        if currency and currency.strip().lower() == "lak":
            return "LAK"
        return "LAK"

    @staticmethod
    def _is_placeholder(name: str) -> bool:
        lowered = name.lower()
        return "gift card" in lowered or "service" in lowered or "서비스" in lowered

    @staticmethod
    def _category_from_url(url: str) -> str | None:
        path = urlparse(url).path
        marker = "/shop/category/"
        if marker not in path:
            return None
        slug = path.split(marker, 1)[1].strip("/")
        if not slug:
            return None
        return slug.rsplit("-", 1)[0].replace("-", " ").title()

    @staticmethod
    def _shop_page_number(href: str) -> int:
        path = urlparse(href).path.rstrip("/")
        if "/shop/page/" not in path:
            return 1
        page = path.rsplit("/", 1)[-1]
        try:
            return int(page)
        except ValueError:
            return 1
