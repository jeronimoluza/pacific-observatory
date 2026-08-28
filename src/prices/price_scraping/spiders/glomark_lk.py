"""
Spider for Glomark (Sri Lanka) — https://glomark.lk/.

Server-rendered category pages (Custom PHP, ZENEDGE-fronted, no WAF hit).
The site's own shop-now nav exposes 487 category/subcategory URLs of shape
/<path>/c/<id> (category) and /<path>/<sub>/sc/<id> (subcategory); most `c`
URLs are pure parents whose products are already covered by their `sc`
children, so the crawl list here (`_glomark_lk_categories.txt`, 398 lines)
keeps only leaf `c` categories (no `sc` children) plus every `sc` URL, to
stay under the 500-line file cap without losing catalog coverage.

Each product card on a category page carries name + price directly:
`<a href="/<slug>/p/<id>">...product-title"><span>NAME</span>...
class="price"><strong class="clr-txt">Rs 520.00</strong>`. No numeric
`?page=` pagination observed on probed categories (page=2 on a 5-product
subcategory returned byte-identical content) — categories appear to render
their full product set in one response.

Re-verified live 2026-08-06: /bakery/bread/c/118 -> 200, 862KB, 10 real
product cards incl. 'Cheese And Garlic Bread 350G' Rs 520.00.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

_TRAILING_ID_RE = re.compile(r"/(?:c|sc)/\d+$")

logger = logging.getLogger(__name__)

_BASE = "https://glomark.lk"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_glomark_lk_categories.txt"
_CARD_RE = re.compile(
    r'href="(/[a-z0-9-]+/p/(\d+))">\s*<div class="product-media">.*?'
    r'product-title">\s*<span[^>]*>([^<]*)</span>.*?'
    r'class="price">\s*<strong class="clr-txt">\s*Rs\.?\s*([0-9,]+\.?[0-9]*)',
    re.S,
)


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class GlomarkLkSpider(scrapy.Spider):
    name = "glomark_lk"
    allowed_domains = ["glomark.lk"]
    currency = "LKR"
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
        for path in _load_categories():
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_category,
                meta={"category_path": path},
            )

    def parse_category(self, response):
        category = _TRAILING_ID_RE.sub("", response.meta["category_path"])
        cards = _CARD_RE.findall(response.text)
        logger.info(f"glomark_lk: {category} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, product_id, name, price in cards:
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": category.strip("/").replace("/", " > "),
                "price": price.replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
