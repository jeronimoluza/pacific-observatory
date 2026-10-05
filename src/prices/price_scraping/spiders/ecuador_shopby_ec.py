"""Scrape current promoted-product cards from ShopBy Ecuador."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urlparse

import scrapy


class EcuadorShopbyEcSpider(scrapy.Spider):
    name = "ecuador_shopby_ec"
    allowed_domains = ["shopby.com.ec", "www.shopby.com.ec"]
    start_urls = ["https://shopby.com.ec/"]

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.xpath(
            '//div[contains(concat(" ", normalize-space(@class), " "), " group ")]'
            '[.//a[contains(@href, "/producto/")]]'
            '[.//p[contains(normalize-space(.), "Ahora:")]]'
        )
        for card in cards:
            href = (card.xpath('.//a[contains(@href, "/producto/")]/@href').get() or "").strip()
            price_text = (
                card.xpath('.//p[contains(normalize-space(.), "Ahora:")]/span/text()').get() or ""
            ).strip()
            slug = unquote(urlparse(href).path.rstrip("/").rsplit("/", 1)[-1])
            id_match = re.search(r"-([0-9a-f]{13})$", slug)
            price_match = re.search(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)", price_text)
            if not (id_match and price_match):
                continue
            try:
                price = Decimal(price_match.group(1))
            except InvalidOperation:
                continue
            if price <= 0:
                continue
            name_slug = slug[: id_match.start()]
            name = " ".join(name_slug.replace("-", " ").split()).title()
            if not name:
                continue
            yield {
                "product_id": id_match.group(1),
                "product_name": name[:500],
                "price": str(price),
                "currency": "USD",
                "country": "Ecuador",
                "sector": "consumer_goods",
                "available": True,
                "url": href,
                "language": "es",
                "scraped_at_utc": scraped_at,
                "price_caveat": "Current price from the storefront's promoted-product 'Ahora' card.",
            }
