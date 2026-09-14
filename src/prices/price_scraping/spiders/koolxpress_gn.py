"""KoolXpress Guinea public marketplace article pages (GNF)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_ROOT_URL = "https://koolxpress.com/"
_PRICE_RE = re.compile(r"([0-9][0-9\s,.]*)")
_ARTICLE_RE = re.compile(r"/article/(ART-[A-Za-z0-9_-]+)(?:[/?#]|$)", re.I)


def _clean(value: object) -> str:
    if isinstance(value, (list, tuple)):
        value = " ".join(map(str, value))
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _price(value: object) -> str | None:
    match = _PRICE_RE.search(_clean(value))
    if not match:
        return None
    raw = match.group(1).replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        return None
    return f"{amount:.2f}" if amount > 0 else None


class KoolxpressGnSpider(scrapy.Spider):
    name = "koolxpress_gn"
    allowed_domains = ["koolxpress.com"]
    currency = "GNF"
    language = "fr"
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.25}

    async def start(self):
        yield scrapy.Request(_ROOT_URL, callback=self.parse_listing)

    def parse_listing(self, response):
        # Crawl only observed first-party listing expansion routes.
        for href in response.css("a[href*='/article/']::attr(href)").getall():
            if _ARTICLE_RE.search(href):
                yield response.follow(href, self.parse_article)
        for href in response.css("a[href*='/shop/']::attr(href)").getall():
            yield response.follow(href, self.parse_listing)

    def parse_article(self, response):
        article = _ARTICLE_RE.search(response.url)
        name = _clean(response.css("h1::text, .product-title::text, .article-title::text").getall())
        price = _price(
            response.css(
                "p.text-3xl::text, .product-price ::text, .price ::text, [itemprop='price']::attr(content)"
            ).getall()
        )
        if not article or not name or not price:
            return
        list_price = _price(response.css("p.line-through::text, .old-price ::text, .regular-price ::text, del ::text").getall())
        category = _clean(response.css("nav a::text, .breadcrumb a::text").getall()[-1:]) or None
        brand = _clean(response.xpath("//*[contains(normalize-space(.), 'Marque :')]/span[contains(@class, 'font-medium')]/text()").getall()) or None
        shop = _clean(response.css(".shop-name ::text, .seller-name ::text, [class*='shop'] a::text").getall()) or None
        state = _clean(response.css(".stock ::text, .availability ::text").getall()).lower()
        yield {
            "product_id": article.group(1).upper(), "product_name": name[:500],
            "category": category, "brand": brand, "store": shop,
            "price": price, "list_price": list_price, "currency": self.currency,
            "available": not any(word in state for word in ("rupture", "out of stock", "indisponible")),
            "locality": "Conakry", "url": response.url.split("?", 1)[0],
            "language": self.language, "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
