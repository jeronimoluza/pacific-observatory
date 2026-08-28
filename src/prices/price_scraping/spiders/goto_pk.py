"""
Spider for goto.com.pk — Pakistan general online retailer (Karachi/Lahore/
Islamabad delivery per its own footer copy).

SSL cert is expired (curl -v fails without -k; not a WAF, a cert-maintenance
issue) — this spider disables TLS verification. Custom PHP storefront with
Magento-flavoured theme classes (price-box, product-name); /rest/V1/products
and /graphql both come back as the normal HTML shell (not a real API), so
this is a genuine HTML scrape, not a hidden Magento API.

Category landing pages (e.g. /grocery) embed a schema.org ItemList JSON-LD
plus ~90 product cards (`div.product-name h2 a` -> PDP url); query params
(?page=2, ?limit=200) are all silently ignored and re-render page 1, so
there is no working pagination — coverage per category is capped at the
first ~90 cards server-rendered. PDPs embed a schema.org Product JSON-LD
with sku/name/category (a '>'-joined breadcrumb string)/offers
(price/priceCurrency/availability), confirmed live 2026-08-17: 'Nestle
Everyday 1000gm' -> PKR 910.00, sku GMDELO3015814, category 'Grocery >
Fresh & Dairy > Milk & Milk Produce'. The two page types are told apart by
the JSON-LD @type (Product vs ItemList), so one parse callback handles both:
category pages yield more PDP requests, PDPs yield items.

Category seeds seen live from the homepage nav: grocery, mobile-phones,
health-beauty, home-lifestyle, makeup, mens-fashion, womens-fashion,
boys-clothing, girls-clothing, computing-gaming, cooling-air-treatment,
digital-cameras, drone, exercise-fitness, fitness-smart-watches,
food-supplements, security-cameras, small-appliances, smart-phones,
smart-tv, tvs-home-appliances, vacuums-floor-care, refrigerators-freezers,
led-tvs-1996, mens-fragrances, womens-fragrances, baby-toys-kids,
mens-tshirts, online-grocery-shop.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://goto.com.pk"
_CATEGORY_SEEDS = [
    "/grocery",
    "/online-grocery-shop",
    "/mobile-phones",
    "/smart-phones",
    "/health-beauty",
    "/makeup",
    "/home-lifestyle",
    "/mens-fashion",
    "/womens-fashion",
    "/boys-clothing",
    "/girls-clothing",
    "/mens-tshirts",
    "/computing-gaming",
    "/cooling-air-treatment",
    "/digital-cameras",
    "/drone",
    "/exercise-fitness",
    "/fitness-smart-watches",
    "/food-supplements",
    "/security-cameras",
    "/small-appliances",
    "/smart-tv",
    "/tvs-home-appliances",
    "/vacuums-floor-care",
    "/refrigerators-freezers",
    "/led-tvs-1996",
    "/mens-fragrances",
    "/womens-fragrances",
    "/baby-toys-kids",
]
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)
_CARD_LINK_RE = re.compile(
    r'class="product-name">\s*<h2>\s*<a[^>]*href="([^"]+)"', re.DOTALL
)


class GotoPkSpider(scrapy.Spider):
    name = "goto_pk"
    allowed_domains = ["goto.com.pk", "www.goto.com.pk"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    # goto.com.pk's TLS cert is expired; the project-wide RandomBrowserMiddleware
    # already sets meta["impersonate"] on every request, so disabling curl_cffi's
    # verification just means adding impersonate_args (precedent: mojsupermarket_me.py,
    # a different TLS defect fixed with a custom CA bundle via the same mechanism).
    _META = {"impersonate_args": {"verify": False}}

    def start_requests(self):
        for path in _CATEGORY_SEEDS:
            yield scrapy.Request(
                urljoin(_BASE, path), callback=self.parse_page, meta=self._META
            )

    def parse_page(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break

        if product:
            yield from self._yield_item(response, product)
            return

        for href in _CARD_LINK_RE.findall(response.text):
            yield scrapy.Request(
                urljoin(response.url, href), callback=self.parse_page, meta=self._META
            )

    def _yield_item(self, response, product):
        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", "0", "0.00"):
            return

        category = product.get("category")
        if isinstance(category, str) and ">" in category:
            category = category.rsplit(">", 1)[-1].strip()

        yield {
            "product_id": product.get("sku") or response.url,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(offers.get("availability", "")).endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
