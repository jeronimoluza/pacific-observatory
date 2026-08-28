"""
Spider for supermarket.ie (Ireland) —
https://www.supermarket.ie/compare/supermarket-prices-ireland.

Real retailer-sourced basket-comparison tool (Tesco/Dunnes/SuperValu/Aldi),
not a survey publisher. It is NOT an itemized catalogue: the page is a
single Next.js SSR comparison built from a 524-product internal basket,
re-verified live 2026-08-06 (all figures below are raw HTML text, not a
hydration payload -- `<h2>Price comparison by category</h2>` etc.). A
`/api/products` REST endpoint exists (allowed in robots.txt) but always
returns the same static 4-item teaser feed regardless of query params --
not usable for coverage.

The page itself carries three grains, all emitted here as aggregate rows
(category=None marks the two total tiers):
  1. Per-store overall weekly-basket totals (4 rows).
  2. Per-store per-category subtotals (14 categories x up to 4 stores).
  3. A ~42-item illustrative sample with per-store prices (3 stores each);
     this is the only itemized grain and it is a small fixed sample, not
     the full 524-product basket.
Single-page whole-catalog walk (no pagination -- this is the entire public
surface). Scaffolded as analytical_role=aggregate_proxy / channel=null,
mirroring the livingcost/expatistan aggregate-proxy precedent -- per the
source shard this does not count toward per-leaf classifier coverage.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://www.supermarket.ie/compare/supermarket-prices-ireland"

_OVERALL_RE = re.compile(
    r'<div class="font-bold text-sm mb-2"[^>]*>([^<]+)</div>'
    r'<div class="text-2xl font-bold mb-1"[^>]*>€([0-9.]+)</div>',
)
_CATEGORY_BLOCK_RE = re.compile(
    r'<h3 class="font-semibold text-\[#2F2F2E\]">([^<]+)</h3>(.*?)'
    r"(?=<h3 class=\"font-semibold|<h2 class=\"text-xl font-bold text-\[#2F2F2E\] mb-2\">Get a personalised)",
    re.S,
)
_SUBTOTAL_RE = re.compile(
    r'<div class="text-\[11px\] font-medium mb-0\.5 truncate"[^>]*>([^<]+)</div>'
    r'<div class="text-sm font-bold"[^>]*>€([0-9.]+)</div>'
)
_PRODUCT_ROW_RE = re.compile(
    r'<span class="text-\[#5c5b5b\] truncate flex-1">([^<]+)</span>'
    r'<div class="flex gap-2 flex-shrink-0 ml-2 overflow-x-auto">(.*?)</div></div>'
)
_PRODUCT_STORE_PRICE_RE = re.compile(
    r'<span class="text-\[#B2BEC3\]">([^<]+)<!-- --> </span>€([0-9.]+)'
)


class SupermarketIeSpider(scrapy.Spider):
    name = "supermarket_ie"
    allowed_domains = ["supermarket.ie"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for store, price in _OVERALL_RE.findall(response.text):
            n += 1
            product_id = f"overall::{store}"
            yield {
                "product_id": product_id,
                "product_name": f"{store.strip()} - overall weekly basket total",
                "category": None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        for category, body in _CATEGORY_BLOCK_RE.findall(response.text):
            category = html.unescape(category).strip()
            for store, price in _SUBTOTAL_RE.findall(body):
                n += 1
                product_id = f"category::{category}::{store}"
                yield {
                    "product_id": product_id,
                    "product_name": f"{store.strip()} - {category} category total",
                    "category": category,
                    "price": price,
                    "currency": self.currency,
                    "available": True,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
            for name, stores_html in _PRODUCT_ROW_RE.findall(body):
                name = html.unescape(name).strip()
                for store, price in _PRODUCT_STORE_PRICE_RE.findall(stores_html):
                    n += 1
                    product_id = f"product::{category}::{name}::{store}"
                    yield {
                        "product_id": product_id,
                        "product_name": f"{name} ({store.strip()})",
                        "category": category,
                        "price": price,
                        "currency": self.currency,
                        "available": True,
                        "url": f"{response.url}#{product_id}",
                        "language": self.language,
                        "scraped_at_utc": scraped_at,
                    }
        logger.info(f"supermarket_ie: emitted {n} rows")
