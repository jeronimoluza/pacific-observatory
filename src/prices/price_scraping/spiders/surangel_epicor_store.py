"""Surangel (Koror, Palau) Epicor product pages with quantity price tiers."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_SEARCH = "https://shop.surangel.com/inet/storefront/store.php?mode=advancedsearch"
_SEEDS = (
    "https://shop.surangel.com/products/pb--jif-creamy-12oz-12%7C24191.html",
    "https://shop.surangel.com/products/flour--gompyo-wheat-1kg-10%7CGBI10101.html",
    "https://shop.surangel.com/products/corn--eed-whole-kern-15-25oz%7C06-83742.html",
)
_MONEY = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,3})?)\s*/?\s*([A-Za-z]+)", re.I)
_TIER = re.compile(r"(?P<quantity>\d+\s*(?:-|–|to)\s*\d+|\d+\s*\+?)?\s*\$\s*(?P<price>[0-9]+(?:\.[0-9]{1,3})?)\s*/?\s*(?P<unit>[A-Za-z]+)", re.I)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _product_id(url: str) -> str:
    slug = url.rsplit("/", 1)[-1].removesuffix(".html")
    return slug.rsplit("%7C", 1)[-1].rsplit("|", 1)[-1]


class SurangelEpicorStoreSpider(scrapy.Spider):
    name = "surangel_epicor_store"
    allowed_domains = ["shop.surangel.com"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request(_SEARCH, callback=self.parse_discovery)
        for url in _SEEDS:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_discovery(self, response):
        for href in response.css('a[href*="/products/"]::attr(href)').getall():
            yield response.follow(href, self.parse_product)
        for href in response.css('a[rel="next"]::attr(href), a.next::attr(href)').getall():
            yield response.follow(href, self.parse_discovery)

    def parse_product(self, response):
        text = _clean(" ".join(response.css("body *::text").getall()))
        name = _clean(response.css("h1::text, .product-name::text, .product_title::text").get())
        if not name:
            name = _clean(response.xpath('//meta[@property="og:title"]/@content').get())
        tiers = []
        for match in _TIER.finditer(text):
            price, unit = float(match["price"]), match["unit"].upper()
            if price > 0 and unit in {"EA", "LB", "OZ", "KG", "CS", "PK"}:
                tiers.append({"min_quantity": _clean(match["quantity"]) or None,
                              "price": f"{price:.3f}".rstrip("0").rstrip("."), "unit": unit})
        if not tiers:
            match = _MONEY.search(text)
            if not match:
                return
            tiers = [{"min_quantity": None, "price": match[1], "unit": match[2].upper()}]
        retail = tiers[0]
        if not name or not retail["unit"]:
            return
        yield {
            "product_id": _product_id(response.url), "product_name": name[:500],
            "price": retail["price"], "currency": "USD", "unit": retail["unit"],
            "price_tiers": tiers, "retail_tier": retail["min_quantity"],
            "available": "out of stock" not in text.lower(), "locality": "Koror, Palau",
            "url": response.url.split("?", 1)[0], "language": "en",
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
