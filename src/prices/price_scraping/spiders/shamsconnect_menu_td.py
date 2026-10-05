"""ShamsConnect Chad bilingual restaurant menu extractor."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"(?:FCFA|CFA)\s*([0-9][0-9 .]*(?:,[0-9]{1,2})?)|([0-9][0-9 .]*)\s*(?:FCFA|CFA)", re.I)
SKIP_RE = re.compile(r"menu|contact|adresse|address|phone|t\u00e9l|tel|shamsconnect", re.I)


def clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


class ShamsconnectMenuTdSpider(scrapy.Spider):
    name = "shamsconnect_menu_td"
    allowed_domains = ["shamsconnect.com"]
    start_urls = ["https://shamsconnect.com/menu"]
    custom_settings = {"DOWNLOAD_DELAY": 0.5, "CONCURRENT_REQUESTS_PER_DOMAIN": 1}

    def parse(self, response):
        headings = response.css("h1, h2, h3, h4, article, section, li, p")
        seen = set()
        for node in headings:
            text = clean(" ".join(node.css("::text").getall()))
            if not text or SKIP_RE.search(text):
                continue
            match = PRICE_RE.search(text)
            if not match:
                continue
            raw_price = next(value for value in match.groups() if value is not None)
            price = raw_price.replace(" ", "").replace(".", "").replace(",", ".")
            name = clean(PRICE_RE.sub("", text)).strip(" -:|/")
            if not name or len(name) > 160:
                continue
            category = clean(node.xpath("preceding::h2[1]//text() | preceding::h3[1]//text()").get() or "") or None
            key = (name.casefold(), price)
            if key in seen:
                continue
            seen.add(key)
            yield {
                "product_id": f"{name.casefold()}:{price}",
                "product_name": name,
                "price": price,
                "currency": "XAF",
                "category": category,
                "url": response.url,
                "channel": "restaurant_menu",
                "locality": "N'Djamena, Chad",
                "language": "fr/ar",
                "price_raw": raw_price,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
