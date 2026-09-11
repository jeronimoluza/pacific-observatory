"""
Hawkers Cash & Carry (Botswana) -- https://www.hawkersbw.com/

A Botswana wholesale/cash-and-carry FMCG retailer running on Wix Stores.
"Cash & Carry" is a wholesale channel, and the catalogue is genuinely
food-dominant: washing powder, painkillers (Panado), juice boxes,
yoghurt, Nestle products (Barone, Milo), biscuits, tomato sauce,
cigarettes, seasoning, sweets, canned beans, soft drinks -- a classic
wholesale FMCG assortment.

Platform: Wix Stores, same shape as ezeemarket_lr.py (no open commerce
REST API; Wix auto-generates a /store-products-sitemap.xml listing every
live PDP, and each PDP is server-rendered with a schema.org Product
JSON-LD block carrying name/price/currency/availability -- Tier 1A, no
Playwright needed at collection time).

ENUMERABILITY: sitemap MEASURED 2026-09-11 with 339 distinct
/product-page/<slug> URLs -- the whole live catalogue, no pagination
needed (the sitemap itself is the enumeration surface, same pattern as
spar2u_bw's product sitemap).

CURRENCY: BWP, confirmed live from the JSON-LD `offers.priceCurrency`
field on every sampled PDP (e.g. "Mowana 2KG Washing Powder", BWP 44.30)
-- matches countries.yaml's Botswana default.

coicop_classification: classifier, coicop_codes unset -- catalogue spans
food, household cleaning and tobacco, wide by the narrowness rule.
channel: wholesale (Cash & Carry).
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://www.hawkersbw.com/store-products-sitemap.xml"


class HawkersCashCarryBwSpider(scrapy.Spider):
    name = "hawkers_cash_carry_bw"
    allowed_domains = ["hawkersbw.com", "www.hawkersbw.com"]
    currency = "BWP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        yield scrapy.Request(SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        response.selector.remove_namespaces()
        urls = response.xpath("//url/loc/text()").getall()
        logger.info(f"hawkers_cash_carry_bw: {len(urls)} product urls in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        for script in response.css(
            'script[type="application/ld+json"]::text'
        ).getall():
            try:
                data = json.loads(script)
            except json.JSONDecodeError:
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if not isinstance(node, dict) or node.get("@type") != "Product":
                    continue
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = offers.get("price")
                name = node.get("name")
                if not price or not name:
                    continue
                try:
                    if float(price) == 0:
                        continue
                except (TypeError, ValueError):
                    continue
                yield {
                    "product_id": None,
                    "product_name": str(name).strip()[:500],
                    "price": str(price),
                    "currency": offers.get("priceCurrency") or self.currency,
                    "category": None,
                    "url": offers.get("url") or response.url,
                    "scraped_at": response.headers.get("Date", b"").decode(
                        "utf-8"
                    ),
                }
