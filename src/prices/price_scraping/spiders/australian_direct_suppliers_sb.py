"""Solomon Islands consumer-goods catalogue from Australian Direct Suppliers."""
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy
from bs4 import BeautifulSoup


class AustralianDirectSuppliersSbSpider(scrapy.Spider):
    name = "australian_direct_suppliers_sb"
    allowed_domains = ["australiandirectsuppliers.com"]
    start_urls = [
        "https://www.australiandirectsuppliers.com/category/smartphones",
    ]
    currency = "SBD"
    language = "en"

    def parse(self, response):
        for item in self._items_from_html(response.text):
            yield item
        next_url = response.css('link[rel="next"]::attr(href)').get()
        if next_url:
            yield scrapy.Request(response.urljoin(next_url), callback=self.parse)

    @classmethod
    def _items_from_html(cls, html_text):
        scraped_at = datetime.now(timezone.utc).isoformat()
        soup = BeautifulSoup(html_text, "html.parser")
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or script.get_text())
            except (TypeError, json.JSONDecodeError):
                continue
            nodes = data if isinstance(data, list) else data.get("itemListElement", [])
            for entry in nodes:
                node = entry.get("item", entry) if isinstance(entry, dict) else {}
                if node.get("@type") != "Product":
                    continue
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if offers.get("priceCurrency") != cls.currency:
                    continue
                try:
                    price = float(offers.get("price"))
                except (TypeError, ValueError):
                    continue
                url = offers.get("url") or node.get("url")
                if not node.get("name") or not url or price <= 0:
                    continue
                yield {
                    "product_name": node["name"].strip(),
                    "price": price,
                    "currency": cls.currency,
                    "url": url,
                    "product_id": urlparse(url).path.rstrip("/").rsplit("/", 1)[-1],
                    "country": "Solomon Islands",
                    "locality": "Solomon Islands",
                    "sector": "consumer_goods",
                    "available": True,
                    "language": cls.language,
                    "scraped_at_utc": scraped_at,
                }
