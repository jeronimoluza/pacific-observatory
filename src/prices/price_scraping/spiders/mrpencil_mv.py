"""Extract visible, positive-priced Mr Pencil WooCommerce product cards."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


URL = "https://mrpencil.mv/shop/"


def clean(parts: list[str]) -> str:
    return " ".join(" ".join(parts).replace("\xa0", " ").split())


def amount(parts: list[str]) -> str | None:
    match = re.search(r"\d+(?:[.,]\d{1,2})?", clean(parts).replace(",", ""))
    if not match or float(match.group()) <= 0:
        return None
    return match.group()


class MrPencilMvSpider(scrapy.Spider):
    name = "mrpencil_mv"
    allowed_domains = ["mrpencil.mv"]
    custom_settings = {"DOWNLOAD_DELAY": 0.5, "CONCURRENT_REQUESTS_PER_DOMAIN": 1}

    async def start(self):
        yield scrapy.Request(URL, callback=self.parse)

    def parse(self, response):
        seen: set[str] = set()
        for card in response.css("li.product"):
            name = clean(card.css("h2.woocommerce-loop-product__title ::text").getall())
            currency = clean(card.css(".woocommerce-Price-currencySymbol ::text").getall())
            price = amount(card.css(".woocommerce-Price-amount ::text").getall())
            url = card.css("h2.woocommerce-loop-product__title a::attr(href)").get()
            product_id = card.attrib.get("data-product_id") or ""
            if not product_id:
                product_id = next((value[5:] for value in card.attrib.get("class", "").split() if value.startswith("post-")), "")
            if not name or currency != "MVR" or not price or not url:
                continue
            canonical_url = response.urljoin(url)
            key = product_id or canonical_url
            if key in seen:
                continue
            seen.add(key)
            yield {
                "product_id": f"mrpencil:{key}",
                "product_name": name,
                "price": price,
                "currency": currency,
                "channel": "retailer",
                "locality": "Maldives",
                "url": canonical_url,
                "language": "en",
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
