"""FAFECA Marketplace (Bangui): server-rendered product cards and PDPs."""
from __future__ import annotations

import re
from datetime import datetime, timezone
import scrapy

_START = [
    "https://marketplace.fafeca.org/category/agri-food",
    "https://marketplace.fafeca.org/category/health-beauty",
    "https://marketplace.fafeca.org/category/home-furnishings",
    "https://marketplace.fafeca.org/category/fashion-accessories",
]
_PRICE = re.compile(r"(?:XAF|FCFA|CFA)\s*([0-9][0-9\s,.]*)|([0-9][0-9\s,.]*)\s*(?:XAF|FCFA|CFA)", re.I)

def clean(value): return " ".join((value or "").replace("\\xa0", " ").split())
def price(value):
    hit = _PRICE.search(clean(value))
    if not hit:
        return None
    amount = (hit.group(1) or hit.group(2)).replace(" ", "").replace(",", "")
    return amount if amount and float(amount) > 0 else None

class CentralAfricanRepublicFafecaMarketplaceSpider(scrapy.Spider):
    name = "central_african_republic_fafeca_marketplace"
    allowed_domains = ["marketplace.fafeca.org"]
    start_urls = _START
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.5}

    def parse(self, response):
        # Only product-card links are followed: nav/cart prices must never become observations.
        for card in response.css("article, .product, .product-card, [class*='product']"):
            href = card.css("a[href*='/product/']::attr(href)").get()
            text = clean(" ".join(card.css("::text").getall()))
            value = price(text)
            name = clean(card.css("h2::text, h3::text, .product-title::text, [class*='title']::text").get())
            if not name and href:
                name = href.rstrip("/").rsplit("/", 1)[-1].rsplit("-", 1)[0].replace("-", " ").title()
            if href and name and value:
                yield {
                    "product_id": href.rstrip("/").rsplit("/", 1)[-1],
                    "product_name": name[:500],
                    "price": value,
                    "currency": "XAF",
                    "url": response.urljoin(href).split("?", 1)[0],
                    "country": "Central African Republic",
                    "category": clean(response.css("h1::text, .category-title::text").get()) or None,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            if href:
                yield response.follow(href, self.parse_product)
        next_url = response.css("a[rel='next']::attr(href), .pagination a.next::attr(href)").get()
        if next_url: yield response.follow(next_url, self.parse)

    def parse_product(self, response):
        root = response.css("main, .product-detail, .product, article").xpath("string(.)").get() or response.xpath("string(//body)").get() or ""
        name = clean(response.css("h1::text, .product-title::text").get())
        value = price(root)
        if not (name and value and float(value) > 0): return
        yield {"product_id": response.url.rstrip("/").rsplit("/", 1)[-1], "product_name": name[:500],
               "price": value, "currency": "XAF", "url": response.url.split("?",1)[0],
               "country": "Central African Republic", "category": clean(response.css(".breadcrumb a::text").getall()[-1] if response.css(".breadcrumb a::text").getall() else "") or None,
               "scraped_at_utc": datetime.now(timezone.utc).isoformat()}
