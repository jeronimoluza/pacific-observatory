"""Ponton Shop's server-rendered Congo-Brazzaville product rail."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"([0-9][0-9 ]*)\s*FCFA", re.I)


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


class PontonShopCgSpider(scrapy.Spider):
    name = "ponton_shop_cg"
    allowed_domains = ["ponton-shop.fr"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request("https://ponton-shop.fr/")

    def parse(self, response):
        seen = set()
        # The current response has an injected empty document before its doctype.
        document = response.text
        doctype = document.find("<!DOCTYPE")
        selector = scrapy.Selector(text=document[doctype:] if doctype >= 0 else document)
        for card in selector.css(".product-card"):
            href = card.css('a[href*="/product/"]::attr(href)').get()
            name = clean(card.css("h3 a::text").get()).removeprefix("Voir ").strip()
            match = PRICE_RE.search(clean(" ".join(card.css(".card-text::text").getall())))
            if not (href and name and match):
                continue
            url = response.urljoin(href).split("#", 1)[0]
            product_id = url.rstrip("/").rsplit("/", 1)[-1]
            if product_id in seen:
                continue
            seen.add(product_id)
            price = match.group(1).replace(" ", "")
            if float(price) <= 0:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": price,
                "currency": "XAF",
                "country": "Republic of the Congo",
                "sector": "consumer_goods",
                "url": url,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
