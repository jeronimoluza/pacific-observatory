"""
Ezee Market (Monrovia, Liberia) -- https://ezeemarket.wixsite.com/ezeemarket
(production custom domain www.ezeemarket.biz times out from a8 on every
probe; the wixsite.com preview/staging domain is live and serves
identical content, so this spider targets that host).

"Online Shopping in Liberia | Ezee Market -- Shop Online for All Kinds of
Products" -- a general Wix Stores marketplace (groceries, beauty, home
goods), not purely food. BUT its "Grocery" collection
(/grocery, totalCount=680 in the page's own embedded warmup JSON) is a
genuinely large, food-dominant vertical: rice (many brands/origins),
Maggi/MDH seasoning cubes and masalas, red palm oil, sour cream, cheese,
luncheon meat, cooking oats -- directly relevant to Liberia's cereals&bread,
oils&fats, dairy&eggs, and ready-meals/condiments gap categories.

Platform: Wix Stores. No open commerce REST API found (same as
neufeldhof_li -- Wix's storefront data API needs a site-scoped token not
exposed here). Working route instead: Wix auto-generates
/store-products-sitemap.xml listing every live product URL (2,683 <loc>
entries across the WHOLE site, not just Grocery -- confirmed live
2026-09-11), and each product page is server-rendered with a schema.org
Product JSON-LD block carrying name/price/currency/availability -- Tier
1A, no Playwright needed at collection time. Sample (pinto beans PDP):
  {"@type":"Product","name":"Heartland premium triple clean pinto beans",
   "offers":{"@type":"Offer","priceCurrency":"USD","price":"60",
   "availability":"https://schema.org/InStock", ...}}

ENUMERABILITY: confirmed via the /grocery collection gallery page's own
pagination (?page=1 vs ?page=2 return fully disjoint product-name sets --
page1 starts "Ezee Combo #5"/"Nura...Oats", page2 starts "MDH Chicken
Curry Masala") AND via the sitemap itself, which lists 2,683 distinct PDP
URLs city-wide. This spider crawls the full sitemap (not scoped to
/grocery) -- the catalog spans groceries, beauty and other departments
(a "Fenty Beauty" and a "body cream" PDP were also observed in the
sitemap sample), so `channel: dept-store` and `coicop_codes` unset,
matching the wide-catalog convention used elsewhere in this repo
(le_jumbo, tsengisa_africa) for mixed general-merchandise storefronts;
the classifier assigns COICOP per product rather than the manifest
declaring one COICOP class for the whole source.

CURRENCY: USD confirmed live from the JSON-LD `priceCurrency` field on
every sampled PDP -- Liberia is a dual-currency (USD/LRD) economy and
this retailer prices in USD, noted rather than silently assumed.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://ezeemarket.wixsite.com/ezeemarket/store-products-sitemap.xml"


class EzeemarketLrSpider(scrapy.Spider):
    name = "ezeemarket_lr"
    allowed_domains = ["ezeemarket.wixsite.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        yield scrapy.Request(SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        response.selector.remove_namespaces()
        urls = response.xpath("//url/loc/text()").getall()
        logger.info(f"ezeemarket_lr: {len(urls)} product urls in sitemap")
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
