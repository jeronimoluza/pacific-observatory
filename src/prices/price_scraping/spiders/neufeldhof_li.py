"""
Neufeldhof Hofladen (Vaduz, Liechtenstein) -- https://www.neufeldhof.li/.

Farm shop, Wix Stores platform -- NOT WooCommerce/Ecwid despite an
earlier fingerprint pass flagging "ecwid" strings on the homepage (those
are references to Wix's own "ecwid.com/wix/app/*" storefront widget
IDs, not a standalone Ecwid REST API; no open Ecwid endpoint exists).
No Wix commerce REST API was found open either -- Wix's own storefront
data API requires a site-scoped token not exposed on this tenant.

Confirmed working route instead: Wix auto-generates
/store-products-sitemap.xml listing every live product URL, and each
product page is server-rendered with a schema.org Product JSON-LD block
carrying name/price/currency/availability -- Tier 1A, no Playwright
needed at collection time (one was run to confirm no better API exists;
see notes in the batch report).

  https://www.neufeldhof.li/store-products-sitemap.xml -- 4 <loc> entries
  (verified live 2026-09-11): two egg listings, one alpine cheese, one
  peppermint syrup.
  Sample JSON-LD (product-page/alpkäse...): {"@type":"Product",
    "name":"Alpkäse Pradamée 2024 ca. 200 g",
    "offers":{"price":"5.6","priceCurrency":"CHF","availability":
    ".../InStock"}}

Tiny catalog (4 SKUs) -- the sitemap's own <lastmod> reads 2024-08-26,
but the live product content is current (the sitemap slug still says
"2020"/"2024" vintages while the JSON-LD price/name reflect the current
listing), so this is a small-but-real farm-shop catalog, not a stale or
fake one. There is no second page to prove distinctness against --
the whole catalog fits on the sitemap in one response -- so
enumerability here is "every sitemap URL is a distinct, real product",
not page1-vs-page2 pagination.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://www.neufeldhof.li/store-products-sitemap.xml"


class NeufeldhofLiSpider(scrapy.Spider):
    name = "neufeldhof_li"
    allowed_domains = ["neufeldhof.li"]
    currency = "CHF"
    language = "de"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        yield scrapy.Request(SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        response.selector.remove_namespaces()
        urls = response.xpath("//url/loc/text()").getall()
        logger.info(f"neufeldhof_li: {len(urls)} product urls in sitemap")
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
