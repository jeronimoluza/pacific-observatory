"""
Connections Curacao -- https://connectionscuracao.net/

Punda / Otrobanda (Willemstad) electronics retailer. The storefront is a
static page whose JS loads data/products.json (list of {name, suffix, price,
category, featured, image}); this spider reads that JSON directly. Prices are
shown as "XCG 549" on the page, so currency is XCG.

The JSON has no per-product URLs, so a stable fragment URL is built from the
name/suffix slug (the dedup pipeline hashes the url).

Page family: API.
"""

import json
import re

import scrapy


class ConnectionsCwSpider(scrapy.Spider):
    name = "connections_cw"
    allowed_domains = ["connectionscuracao.net"]
    currency = "XCG"
    language = "en"
    BASE = "https://connectionscuracao.net"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
    }

    def start_requests(self):
        yield scrapy.Request(f"{self.BASE}/data/products.json", callback=self.parse_json)

    def parse_json(self, response):
        for p in json.loads(response.text):
            name, price = p.get("name"), p.get("price")
            if not name or price in (None, ""):
                continue
            suffix = p.get("suffix") or ""
            label = f"{name} {suffix}".strip()
            slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
            yield {
                "product_id": slug,
                "product_name": label,
                "price": str(price),
                "currency": self.currency,
                "category": p.get("category"),
                "url": f"{self.BASE}/#p-{slug}",
                "language": self.language,
            }
