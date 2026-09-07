"""Chemica PNG Odoo storefront for hardware, tools, and home/garden goods."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import scrapy

logger = logging.getLogger(__name__)


class ChemicaBizPgSpider(scrapy.Spider):
    name = "chemica_biz_pg"
    allowed_domains = ["chemica.biz", "www.chemica.biz"]
    currency = "PGK"
    language = "en"

    start_urls = [
        "https://www.chemica.biz/shop/category/hardware-30",
        "https://www.chemica.biz/shop/category/machinery-45",
        "https://www.chemica.biz/shop/category/solar-42",
        "https://www.chemica.biz/shop/category/haus-flat-pack-furniture-54",
    ]
    max_shop_page = 8

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
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

        for href in response.css("ul.pagination a.page-link::attr(href)").getall():
            if self._same_clean_url(response.url, response.urljoin(href)):
                continue
            if self._shop_page_number(href) <= self.max_shop_page:
                yield response.follow(href, callback=self.parse)

    def _parse_card(self, response, card, scraped_at: str):
        href = (
            card.css('a[itemprop="url"]::attr(href)').get()
            or card.css('a[itemprop="name"]::attr(href)').get()
            or card.css('a[href*="/shop/"]::attr(href)').get()
        )
        name = (
            card.attrib.get("aria-label")
            or card.css('a[itemprop="name"]::attr(content)').get()
            or card.css('a[itemprop="name"]::text').get()
            or card.css("h6 a::text, h6::text, h3::text").get()
        )
        prices = card.css(
            'span[aria-label="Sale price"] span.oe_currency_value::text, '
            "div.product_price span.oe_currency_value::text, "
            "span.oe_currency_value::text"
        ).getall()
        product_id = (
            card.css(".o_add_wishlist::attr(data-product-template-id)").get()
            or card.css(".o_add_wishlist::attr(data-product-product-id)").get()
            or card.css('input[name="product_id"]::attr(value)').get()
        )

        if not href or not name or not prices:
            return None

        name = " ".join(name.split())
        price = prices[-1]
        try:
            value = float(str(price).replace(",", ""))
        except ValueError:
            return None
        if value <= 0:
            return None

        parsed = urlparse(response.urljoin(href))
        clean_url = urlunparse(parsed._replace(query="", fragment=""))
        url_id = parsed.path.rstrip("/").rsplit("-", 1)[-1]
        product_id = url_id if url_id.isdigit() else product_id

        return {
            "product_id": str(product_id or clean_url),
            "product_name": name[:500],
            "price": f"{value:.2f}",
            "currency": self.currency,
            "category": self._category_from_url(response.url),
            "url": clean_url,
            "language": self.language,
            "store": "Chemica",
            "scraped_at_utc": scraped_at,
        }

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
        if "/page/" not in path:
            return 1
        page = path.rsplit("/", 1)[-1]
        try:
            return int(page)
        except ValueError:
            return 1

    @staticmethod
    def _same_clean_url(left: str, right: str) -> bool:
        def clean(url: str) -> str:
            parsed = urlparse(url)
            return urlunparse(parsed._replace(query="", fragment="")).rstrip("/")

        return clean(left) == clean(right)
