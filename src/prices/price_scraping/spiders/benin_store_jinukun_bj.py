"""Jinukun Store's server-rendered Benin local-goods catalogue."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"([0-9][0-9\s\u202f,]*)\s*(?:CFA|FCFA)\b", re.I)


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


class BeninStoreJinukunBjSpider(scrapy.Spider):
    name = "benin_store_jinukun_bj"
    allowed_domains = ["store.jinukun.bj"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request("https://store.jinukun.bj/")

    def parse(self, response):
        seen = set()
        for card in response.css(".ec-product-inner"):
            href = card.css('a[href*="/produit/"]::attr(href)').get()
            name = clean(card.css("h5.ec-pro-title::text").get())
            price_text = clean(" ".join(card.css(".new-price ::text, .new-price::text").getall()))
            match = PRICE_RE.search(price_text)
            if not (href and name and match):
                continue
            url = response.urljoin(href).split("#", 1)[0]
            product_id = url.rstrip("/").rsplit("/", 1)[-1]
            if product_id in seen:
                continue
            seen.add(product_id)
            price = match.group(1).replace(" ", "").replace("\u202f", "").replace(",", "")
            if float(price) <= 0:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": price,
                "currency": "XOF",
                "country": "Benin",
                "sector": "consumer_goods",
                "url": url,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
